"""Common constants shared across multiple services."""

# Mapping from trait types to relationship types
TRAIT_TYPE_TO_RELATIONSHIP_MAPPING = {
    "skill": "HAS_SKILL",
    "interest": "INTERESTED_IN",
    "preference": "PREFERS",
    "like": "LIKES",
    "dislike": "DISLIKES",
    "attribute": "HAS_ATTRIBUTE"
} 