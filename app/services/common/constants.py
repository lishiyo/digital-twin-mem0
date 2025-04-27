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

# Valid relationship types for entity connections
RELATIONSHIP_TYPES = [
    "ASSOCIATED_WITH",    # Generic association between entities
    "HAS_MEMBER",         # Organization has a person as member
    "RELATED_TO",         # Generic relation between people
    "LOCATED_IN",         # Entity is located in a place
    "BASED_IN",           # Organization is based in a location
    "CREATED",            # Person created a document/product
    "CREATED_BY",         # Document/product created by person
    "PARTICIPATED_IN",    # Person participated in an event
    "INVOLVED",           # Entity was involved in something
    "ORGANIZED",          # Organization organized an event
    "ORGANIZED_BY",       # Event organized by an organization  
    "OCCURRED_ON",        # Event occurred on a date
    "PUBLISHED_ON",       # Document published on a date
    "PUBLISHED",          # Organization published a document
    "PUBLISHED_BY",       # Document published by organization
    "PRODUCED",           # Organization produced a product
    "PRODUCED_BY",        # Product produced by organization
    "MENTIONED_WITH",     # Default for co-occurrence
    "WORKS_FOR",          # Person works for organization
    "FOUNDED",            # Person founded organization
    "FOUNDED_BY",         # Organization founded by person
    "OWNS",               # Entity owns another entity
    "OWNED_BY",           # Entity owned by another entity
    "SUCCEEDED",          # Entity succeeded another entity
    "SUCCEEDED_BY",       # Entity succeeded by another entity
    # Trait relationships
    "HAS_SKILL",          # Entity has a skill
    "INTERESTED_IN",      # Entity is interested in another entity
    "PREFERS",            # Entity prefers another entity
    "DISLIKES",           # Entity dislikes another entity
    "LIKES",              # Entity likes another entity
    "HAS_ATTRIBUTE",      # Entity has an attribute
]

# Entity types mapping for NLP extraction
ENTITY_TYPE_MAPPING = {
    "PERSON": "Person",
    "ORG": "Organization",
    "GPE": "Location",
    "LOC": "Location",
    "PRODUCT": "Product",
    "WORK_OF_ART": "Document",
    "EVENT": "Event",
    "DATE": "Date",
    "TIME": "Time",
    "MONEY": "Money",
    "PERCENT": "Percent",
    "NORP": "Group",  # Nationalities, religious or political groups
    "FAC": "Facility",  # Buildings, airports, highways, bridges, etc.
    "LAW": "Legal",  # Named documents made into laws
    "LANGUAGE": "Language",
    "ORDINAL": "Ordinal",
    "CARDINAL": "Cardinal",
    "QUANTITY": "Quantity",
    "NAMED_BEING": "NamedBeing", # e.g. animals, plants, non-human entities
    # Trait types
    "ATTRIBUTE": "Attribute",
    "INTEREST": "Interest",
    "SKILL": "Skill",
    "PREFERENCE": "Preference",
    "LIKE": "Like",
    "DISLIKE": "Dislike"
}

# Important entity types that we want to prioritize and preserve
IMPORTANT_ENTITY_TYPES = ["Person", "Organization", "Location", "Product", "Event", "Date", "Time", "Preference", "Like", "Dislike", "Skill", "Interest", "Attribute"] 