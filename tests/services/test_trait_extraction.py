"""Tests for the trait extraction service."""

import pytest
from unittest.mock import MagicMock, patch
import json
from datetime import datetime

from app.services.traits import TraitExtractionService, Trait


def test_trait_class():
    """Test the Trait class."""
    trait = Trait(
        trait_type="skill",
        name="Python programming",
        confidence=0.9,
        evidence="I've been programming in Python for 5 years",
        source="chat",
        source_id="msg123",
        context="Coding discussion",
        strength=0.8
    )
    
    assert trait.trait_type == "skill"
    assert trait.name == "Python programming"
    assert trait.confidence == 0.9
    assert trait.evidence == "I've been programming in Python for 5 years"
    assert trait.source == "chat"
    assert trait.source_id == "msg123"
    assert trait.context == "Coding discussion"
    assert trait.strength == 0.8
    
    # Test to_dict method
    trait_dict = trait.to_dict()
    assert trait_dict["trait_type"] == "skill"
    assert trait_dict["name"] == "Python programming"
    assert trait_dict["confidence"] == 0.9
    assert trait_dict["source"] == "chat"
    assert trait_dict["strength"] == 0.8


@patch('app.services.traits.extractors.TraitExtractor.extract_traits')
async def test_trait_extraction_service_process_traits(mock_extract_traits):
    """Test the trait processing functionality of the service."""
    # Create a mock trait extraction service with no DB session
    service = TraitExtractionService()
    
    # Create mock traits
    mock_traits = [
        Trait(
            trait_type="skill",
            name="Python programming",
            confidence=1.0,  # Will be adjusted by source weight
            evidence="I've been programming in Python for 5 years",
            source="chat"
        ),
        Trait(
            trait_type="interest",
            name="Machine learning",
            confidence=0.7,  # Below threshold after adjustment
            evidence="I find machine learning interesting",
            source="chat"
        )
    ]
    
    # Process the traits
    processed_traits = service._process_traits(mock_traits, "chat")
    
    # Since chat source weight is 0.8, the first trait should have adjusted confidence
    # and be included, while the second should be filtered out
    assert len(processed_traits) == 1
    assert processed_traits[0].name == "Python programming"
    assert processed_traits[0].confidence == 0.8  # 1.0 * 0.8 = 0.8


@patch('app.services.traits.service.TraitExtractionService._update_user_profile')
@patch('app.services.traits.service.TraitExtractionService._process_traits')
@patch('app.services.traits.extractors.ChatTraitExtractor.extract_traits')
async def test_extract_traits_chat(mock_chat_extract, mock_process_traits, mock_update_profile):
    """Test extracting traits from chat messages."""
    # Setup mocks
    mock_traits = [
        Trait(
            trait_type="skill",
            name="Python programming",
            confidence=0.9,
            evidence="I've been programming in Python for 5 years",
            source="chat"
        )
    ]
    mock_chat_extract.return_value = mock_traits
    mock_process_traits.return_value = mock_traits
    mock_update_profile.return_value = {"updated": True}
    
    # Create service
    service = TraitExtractionService()
    
    # Call the method
    result = await service.extract_traits(
        content="I've been programming in Python for 5 years",
        source_type="chat",
        user_id="user123",
        metadata={"message_id": "msg123"}
    )
    
    # Verify calls
    mock_chat_extract.assert_called_once()
    mock_process_traits.assert_called_once()
    
    # Check result
    assert result["status"] == "success"
    assert len(result["traits"]) == 1
    assert result["traits"][0]["name"] == "Python programming" 