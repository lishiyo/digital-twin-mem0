import pytest
from app.services.ingestion.entity_extraction import EntityExtractor

@pytest.fixture
def entity_extractor():
    return EntityExtractor()

def test_markdown_filtering(entity_extractor):
    """Test that Markdown syntax is properly filtered out from entity extraction."""
    markdown_text = """
    # Project Update
    
    ## Digital Twin Implementation
    
    The **Microsoft Azure** team completed the initial setup of the digital twin system.
    
    ### Technical Details
    
    - Integration with **IoT Hub** was successful
    - Data is flowing from sensors to the cloud
    
    [Link to documentation](https://example.com)
    
    #### Next Steps
    
    1. Implement data validation
    2. Connect to **Power BI** dashboard
    """
    
    entities = entity_extractor.extract_entities(markdown_text)
    
    # Verify that Markdown symbols aren't extracted as entities
    markdown_symbols = ["#", "##", "###", "####", "-", "*", "[", "]", "(", ")"]
    for entity in entities:
        assert entity["text"].strip() not in markdown_symbols
        assert not entity["text"].strip().startswith("#")
    
    # Verify that actual entities are still extracted
    entity_texts = [entity["text"] for entity in entities]
    assert "Microsoft Azure" in entity_texts
    assert "IoT Hub" in entity_texts
    assert "Power BI" in entity_texts 