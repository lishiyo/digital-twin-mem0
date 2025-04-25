"""Service for extracting traits from various sources and updating user profiles."""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
import json
from collections import defaultdict

from app.db.models.user import User
from app.db.models.user_profile import UserProfile
from app.services.traits.extractors import Trait, TraitExtractor, ChatTraitExtractor, DocumentTraitExtractor

logger = logging.getLogger(__name__)

class TraitExtractionService:
    """Service for extracting traits from various sources and updating user profiles."""
    
    # Confidence thresholds for traits
    MIN_CONFIDENCE_TRAIT = 0.7
    MIN_CONFIDENCE_TRAIT_SKILL = 0.7
    MIN_CONFIDENCE_TRAIT_INTEREST = 0.7
    MIN_CONFIDENCE_TRAIT_PREFERENCE = 0.7
    MIN_CONFIDENCE_TRAIT_DISLIKE = 0.7
    MIN_CONFIDENCE_TRAIT_ATTRIBUTE = 0.7
    
    # Source reliability weights
    SOURCE_WEIGHTS = {
        "chat": 0.9,
        "document": 0.9,
        # Future sources
        "calendar": 0.75,
        "social_media": 0.6,
    }
    
    def __init__(self, db_session: AsyncSession = None):
        """Initialize the service.
        
        Args:
            db_session: Optional database session
        """
        self.db = db_session
        self._extractors = {
            "chat": ChatTraitExtractor(),
            "document": DocumentTraitExtractor(),
        }
    
    async def extract_traits(
        self,
        content: Any,
        source_type: str,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        update_profile: bool = True
    ) -> Dict[str, Any]:
        """Extract traits from content and optionally update the user profile.
        
        Args:
            content: The content to extract traits from
            source_type: Type of source (chat, document, etc.)
            user_id: ID of the user
            metadata: Optional additional metadata
            update_profile: Whether to update the user profile
            
        Returns:
            Dictionary with extraction results, traits returned as trait models
        """
        metadata = metadata or {}
        metadata["user_id"] = user_id
        
        # Check if we have an extractor for this source type
        if source_type not in self._extractors:
            logger.error(f"No extractor found for source type: {source_type}")
            return {
                "status": "error",
                "message": f"Unsupported source type: {source_type}",
                "traits": []
            }
        
        try:
            # Extract traits
            extractor = self._extractors[source_type]
            traits = await extractor.extract_traits(content, metadata)
            logger.info(f"Extracted {len(traits)} traits from {source_type}")
            
            # Process traits, filter out low confidence traits
            processed_traits = self._process_traits(traits, source_type)
            
            # Update user profile only if requested
            profile_updates = {}
            if update_profile and self.db and processed_traits:
                profile_updates = await self._update_user_profile(user_id, processed_traits)
            
            return {
                "status": "success",
                "traits": [t.to_dict() for t in processed_traits],
                "trait_models": processed_traits,
                "source_type": source_type,
                "profile_updates": profile_updates
            }
            
        except Exception as e:
            logger.error(f"Error extracting traits: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "traits": []
            }
    
    def _process_traits(self, traits: List[Trait], source_type: str) -> List[Trait]:
        """Process extracted traits, filtering out low confidence traits.
        
        Args:
            traits: List of extracted traits
            source_type: Type of source
            
        Returns:
            List of processed traits
        """
        processed_traits = []
        
        # Apply source weight to confidence scores
        source_weight = self.SOURCE_WEIGHTS.get(source_type, 0.7)
        
        for trait in traits:
            # Adjust confidence based on source reliability
            adjusted_confidence = trait.confidence * source_weight
            trait.confidence = round(adjusted_confidence, 2)
            
            logger.info(f"Trait {trait.name} has confidence {trait.confidence} after source weight adjustment")
            # Filter by minimum confidence thresholds
            if trait.confidence < self.MIN_CONFIDENCE_TRAIT:
                logger.info(f"Skipping trait {trait.name} with confidence {trait.confidence} (below threshold {self.MIN_CONFIDENCE_TRAIT})")
                continue
                
            # Apply trait-specific confidence thresholds
            if trait.trait_type == "skill" and trait.confidence < self.MIN_CONFIDENCE_TRAIT_SKILL:
                continue
            elif trait.trait_type == "interest" and trait.confidence < self.MIN_CONFIDENCE_TRAIT_INTEREST:
                continue
            elif trait.trait_type == "preference" and trait.confidence < self.MIN_CONFIDENCE_TRAIT_PREFERENCE:
                continue
            elif trait.trait_type == "dislike" and trait.confidence < self.MIN_CONFIDENCE_TRAIT_DISLIKE:
                continue
            elif trait.trait_type == "attribute" and trait.confidence < self.MIN_CONFIDENCE_TRAIT_ATTRIBUTE:
                continue
            
            processed_traits.append(trait)
        
        return processed_traits
    
    async def _update_user_profile(self, user_id: str, traits: List[Trait]) -> Dict[str, Any]:
        """Update user profile with extracted traits.
        
        Args:
            user_id: ID of the user
            traits: List of trait models to add
            
        Returns:
            Dictionary with update results
        """
        if not traits:
            logger.info(f"No traits to update for user {user_id}")
            return {"updated": False, "reason": "no_traits"}
        
        try:
            # Log the number of traits being processed
            logger.info(f"Updating profile for user {user_id} with {len(traits)} traits")
            
            # Query user with profile efficiently - don't load unnecessary relationships
            query = (
                select(User)
                .where(User.id == user_id)
                .options(joinedload(User.profile))
            )
            
            # Execute the query
            result = self.db.execute(query)
            user = result.unique().scalars().first()
            
            if not user:
                logger.warning(f"User {user_id} not found")
                return {"updated": False, "reason": "user_not_found"}
            
            profile = user.profile
            
            if not profile:
                logger.warning(f"Profile for user {user_id} not found")
                return {"updated": False, "reason": "profile_not_found"}
            
            # Update profile with traits
            updates = self._apply_traits_to_profile(profile, traits)
            
            # Commit changes
            self.db.commit()
            
            return {
                "updated": True,
                "updates": updates,
                "trait_count": len(traits)
            }
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating profile for user {user_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return {"updated": False, "reason": str(e)}
    
    def _apply_traits_to_profile(self, profile: UserProfile, traits: List[Trait]) -> Dict[str, Any]:
        """Apply traits to user profile, handling conflicts and merging.
        
        Args:
            profile: UserProfile to update
            traits: List of traits to apply
            
        Returns:
            Dictionary with update statistics
        """
        updates = {
            "skills_added": 0,
            "skills_updated": 0,
            "interests_added": 0,
            "interests_updated": 0,
            "preferences_added": 0,
            "preferences_updated": 0,
            "dislikes_added": 0,
            "dislikes_updated": 0,
            "attributes_added": 0,
            "attributes_updated": 0
        }
        
        try:
            # Initialize profile sections if they don't exist or load from JSON
            skills = profile.skills if isinstance(profile.skills, list) else json.loads(profile.skills or '[]')
            interests = profile.interests if isinstance(profile.interests, list) else json.loads(profile.interests or '[]')
            preferences = profile.preferences if isinstance(profile.preferences, dict) else json.loads(profile.preferences or '{}')
            dislikes = profile.dislikes if isinstance(profile.dislikes, list) else json.loads(profile.dislikes or '[]')
            attributes = profile.attributes if isinstance(profile.attributes, list) else json.loads(profile.attributes or '[]')
            
            # Ensure profile fields are mutable lists/dicts for updates
            profile.skills = list(skills)
            profile.interests = list(interests)
            profile.preferences = dict(preferences)
            profile.dislikes = list(dislikes)
            profile.attributes = list(attributes)

            # Create maps of existing traits for deduplication and confidence checks
            # Store index along with data for easier update/removal
            skill_map = {s.get("name", "").lower(): (idx, s) for idx, s in enumerate(profile.skills) if isinstance(s, dict) and s.get("name")}
            interest_map = {i.get("name", "").lower(): (idx, i) for idx, i in enumerate(profile.interests) if isinstance(i, dict) and i.get("name")}
            preference_map = {}
            for category, prefs_dict in profile.preferences.items():
                if isinstance(prefs_dict, dict):
                    for name, details in prefs_dict.items():
                        if isinstance(details, dict):
                           preference_map[name.lower()] = (category, name, details) # Store category, original name, details
            dislike_map = {d.get("name", "").lower(): (idx, d) for idx, d in enumerate(profile.dislikes) if isinstance(d, dict) and d.get("name")}
            attribute_map = {a.get("name", "").lower(): (idx, a) for idx, a in enumerate(profile.attributes) if isinstance(a, dict) and a.get("name")}
            
            # Track staged additions (items not found in existing maps)
            staged_skills = []
            staged_interests = []
            staged_preferences = defaultdict(dict) # category -> {name: details}
            staged_dislikes = []
            staged_attributes = []

            # --- Step 1: Process incoming traits ---
            for trait in traits:
                trait_type = trait.trait_type.lower()
                name = trait.name.strip()
                confidence = trait.confidence
                evidence = trait.evidence
                strength = trait.strength or 0.7
                source = trait.source
                
                if not name:
                    continue
                
                # Skip low confidence traits
                if confidence < self.MIN_CONFIDENCE_TRAIT:
                    logger.info(f"Skipping trait {name} with confidence {confidence} (below threshold {self.MIN_CONFIDENCE_TRAIT})")
                    continue
                
                name_lower = name.lower()
                
                # Prepare the data structure for the trait
                trait_data = {
                    "name": name,
                    "confidence": confidence,
                    "source": source,
                    "evidence": evidence,
                    "strength": strength,
                    "last_updated": datetime.now().isoformat()
                }

                # Handle each trait type
                if trait_type == "skill":
                    trait_data["proficiency"] = strength
                    if name_lower in skill_map:
                        idx, existing_skill = skill_map[name_lower]
                        # Update existing only if new confidence is higher or equal
                        if confidence >= existing_skill.get("confidence", 0):
                            profile.skills[idx] = trait_data 
                            updates["skills_updated"] += 1
                    else:
                        # Stage trait for addition
                        staged_skills.append(trait_data)
                        updates["skills_added"] += 1
                        
                elif trait_type == "interest":
                    if name_lower in interest_map:
                        idx, existing_interest = interest_map[name_lower]
                        if confidence >= existing_interest.get("confidence", 0):
                            profile.interests[idx] = trait_data
                            updates["interests_updated"] += 1
                    else:
                        staged_interests.append(trait_data)
                        updates["interests_added"] += 1
                        
                elif trait_type == "preference":
                    category = "general" # Default category
                    if name_lower in preference_map:
                        orig_category, orig_name, existing_preference = preference_map[name_lower]
                        if confidence >= existing_preference.get("confidence", 0):
                            # Update directly in the profile's preference dict
                            profile.preferences[orig_category][orig_name] = trait_data
                            updates["preferences_updated"] += 1
                    else:
                        # Stage new preference under its category
                        staged_preferences[category][name] = trait_data
                        updates["preferences_added"] += 1
                    
                elif trait_type == "dislike":
                    if name_lower in dislike_map:
                        idx, existing_dislike = dislike_map[name_lower]
                        if confidence >= existing_dislike.get("confidence", 0):
                            profile.dislikes[idx] = trait_data
                            updates["dislikes_updated"] += 1
                    else:
                        staged_dislikes.append(trait_data)
                        updates["dislikes_added"] += 1
                        
                elif trait_type == "attribute":
                    if name_lower in attribute_map:
                        idx, existing_attribute = attribute_map[name_lower]
                        if confidence >= existing_attribute.get("confidence", 0):
                            profile.attributes[idx] = trait_data
                            updates["attributes_updated"] += 1
                    else:
                        staged_attributes.append(trait_data)
                        updates["attributes_added"] += 1
            
            # Debug log: Print the staged traits
            logger.info(f"adding staged skills: {staged_skills}")
            logger.info(f"adding staged interests: {staged_interests}")
            logger.info(f"adding staged preferences: {staged_preferences}")
            logger.info(f"adding staged dislikes: {staged_dislikes}")
            logger.info(f"adding staged attributes: {staged_attributes}")
            
            # TODO: should we check for dupes here? maybe ask LLM to merge traits + increase confidence?
            
            # --- Step 2: Add staged new traits ---
            if staged_skills:
                profile.skills.extend(staged_skills)
                
            if staged_interests:
                profile.interests.extend(staged_interests)
                
            if staged_dislikes:
                profile.dislikes.extend(staged_dislikes)
                
            if staged_attributes:
                profile.attributes.extend(staged_attributes)
            
            # Merge staged preferences into the profile preferences dictionary
            if staged_preferences:
                for category, new_prefs in staged_preferences.items():
                    if category not in profile.preferences:
                        profile.preferences[category] = {}
                    profile.preferences[category].update(new_prefs)

            # --- Step 3: Conflict Resolution between lists (Interest vs. Dislike) ---
            # Rebuild maps based on the potentially updated lists
            interest_map_final = {i.get("name", "").lower(): (idx, i) for idx, i in enumerate(profile.interests) if isinstance(i, dict) and i.get("name")}
            dislike_map_final = {d.get("name", "").lower(): (idx, d) for idx, d in enumerate(profile.dislikes) if isinstance(d, dict) and d.get("name")}
            
            conflicting_names = set(interest_map_final.keys()) & set(dislike_map_final.keys())
            
            # Keep track of indices to remove to avoid modifying list while iterating
            indices_to_remove_from_interests = set()
            indices_to_remove_from_dislikes = set()

            if conflicting_names:
                logger.warning(f"Found conflicts between interests and dislikes for: {conflicting_names}")
                
                for name_lower in conflicting_names:
                    interest_idx, interest_item = interest_map_final[name_lower]
                    dislike_idx, dislike_item = dislike_map_final[name_lower]
                    
                    # Keep the one with higher or equal confidence
                    if interest_item.get("confidence", 0) >= dislike_item.get("confidence", 0):
                        indices_to_remove_from_dislikes.add(dislike_idx)
                        logger.info(f"Resolving conflict for '{interest_item.get('name')}': Keeping interest, removing dislike.")
                    else:
                        indices_to_remove_from_interests.add(interest_idx)
                        logger.info(f"Resolving conflict for '{dislike_item.get('name')}': Keeping dislike, removing interest.")
                        
                # Filter out the lower confidence items using list comprehension with indices
                if indices_to_remove_from_interests:
                    profile.interests = [item for idx, item in enumerate(profile.interests) if idx not in indices_to_remove_from_interests]
                    # Update the counts to reflect removals
                    updates["interests_added"] -= len(indices_to_remove_from_interests)
                    if updates["interests_added"] < 0:
                        updates["interests_added"] = 0
                
                if indices_to_remove_from_dislikes:
                    profile.dislikes = [item for idx, item in enumerate(profile.dislikes) if idx not in indices_to_remove_from_dislikes]
                    # Update the counts to reflect removals
                    updates["dislikes_added"] -= len(indices_to_remove_from_dislikes)
                    if updates["dislikes_added"] < 0:
                        updates["dislikes_added"] = 0

            # Update metadata
            profile.last_updated_source = f"trait_extraction_{traits[0].source}" if traits else "trait_extraction"
            
            return updates
            
        except Exception as e:
            logger.error(f"Error applying traits to profile: {str(e)}")
            return {"error": str(e)} 