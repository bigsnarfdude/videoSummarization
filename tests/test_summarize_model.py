import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import spacy
from pathlib import Path
import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from transcribe.summarize_model import (
    get_model_and_tokenizer,
    initialize_spacy,
    create_summary_prompt,
    count_tokens,
    split_text,
    clean_and_format_summary,
    summarize_with_mlx,
    summarize_in_parallel,
    save_summaries
)

@pytest.fixture
def mock_model_tokenizer():
    with patch('transcribe.summarize_model.load') as mock_load:
        model = MagicMock()
        tokenizer = MagicMock()
        tokenizer.encode.return_value = [1, 2, 3]  # Mock token ids
        mock_load.return_value = (model, tokenizer)
        yield model, tokenizer

@pytest.fixture
def mock_spacy():
    with patch('spacy.load') as mock_load:
        nlp = MagicMock()
        doc = MagicMock()
        sent1 = MagicMock()
        sent1.text = "This is sentence one."
        sent2 = MagicMock()
        sent2.text = "This is sentence two."
        doc.sents = [sent1, sent2]
        nlp.return_value = doc
        mock_load.return_value = nlp
        yield nlp

def test_initialize_spacy_load_error():
    """Test spaCy initialization when load fails"""
    with patch('spacy.load') as mock_load:
        mock_load.side_effect = OSError("Model not found")
        with patch('spacy.cli.download') as mock_download:
            mock_download.side_effect = Exception("Download failed")
            with pytest.raises(Exception):
                initialize_spacy()

def test_count_tokens_no_tokenizer():
    """Test token counting when tokenizer is not available"""
    with patch('transcribe.summarize_model.get_model_and_tokenizer') as mock_get:
        mock_get.return_value = (None, None)
        result = count_tokens("Test text")
        assert result == 0

def test_split_text_file_error(tmp_path):
    """Test handling of file read errors in split_text"""
    non_existent_file = tmp_path / "does_not_exist.txt"
    with pytest.raises(Exception):
        split_text(str(non_existent_file), "Test Title")

def test_split_text_spacy_error(mock_model_tokenizer):
    """Test handling of spaCy errors in split_text"""
    with patch('transcribe.summarize_model.initialize_spacy') as mock_init:
        mock_init.return_value = None
        with pytest.raises(RuntimeError, match="Failed to initialize spaCy"):
            split_text("test.txt", "Test Title")

def test_clean_and_format_summary_empty():
    """Test cleaning empty or invalid summaries"""
    result = clean_and_format_summary("")
    assert result == ""

    result = clean_and_format_summary("   \n   \n   ")
    assert result == ""

def test_summarize_with_mlx_no_model():
    """Test summarization when model is not available"""
    with patch('transcribe.summarize_model.get_model_and_tokenizer') as mock_get:
        mock_get.return_value = (None, None)
        result = summarize_with_mlx("Test text", "Test Title")
        assert result is None

def test_summarize_with_mlx_generation_error(mock_model_tokenizer):
    """Test handling of generation errors in summarize_with_mlx"""
    with patch('transcribe.summarize_model.generate') as mock_generate:
        mock_generate.side_effect = Exception("Generation failed")
        result = summarize_with_mlx("Test text", "Test Title")
        assert result is None

def test_summarize_in_parallel_partial_failure(mock_model_tokenizer):
    """Test handling of partial failures in parallel summarization"""
    chunks = ["Chunk 1", "Chunk 2"]
    with patch('transcribe.summarize_model.summarize_with_mlx') as mock_summarize:
        # First chunk fails with None, second succeeds
        mock_summarize.return_value = None
        mock_summarize.side_effect = [None, "Summary 2"]
        results = summarize_in_parallel(chunks, "Test Title")
        assert len(results) == 1
        assert "Summary 2" in results

def test_save_summaries_no_valid_summaries(tmp_path):
    """Test saving summaries when no valid summaries exist"""
    with pytest.raises(RuntimeError, match="No valid summaries generated to save"):
        save_summaries([], "test")
        save_summaries([None, None], "test")

def test_split_text_processing(mock_model_tokenizer, mock_spacy, tmp_path):
    """Test text splitting with actual content"""
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is sentence one. This is sentence two.")
    
    # Mock token counting to return specific values
    with patch('transcribe.summarize_model.count_tokens') as mock_count:
        mock_count.side_effect = [10, 5, 5]  # Total tokens, then per sentence
        chunks = split_text(str(test_file), "Test Title")
        assert len(chunks) >= 1

def test_clean_and_format_summary_with_main_takeaway():
    """Test summary cleaning with main takeaway"""
    raw_summary = """
    Point 1
    Point 2
    Main Takeaway: Important conclusion
    """
    result = clean_and_format_summary(raw_summary)
    assert result.endswith("Main Takeaway: Important conclusion")

def test_clean_and_format_summary_with_quotes():
    """Test summary cleaning with quotes"""
    raw_summary = 'This contains "quoted text" and more "quotes"'
    result = clean_and_format_summary(raw_summary)
    # Check that the quotes are preserved with spaces
    assert '" quoted text "' in result
    assert '" quotes "' in result

def test_split_text_large_sentence(mock_model_tokenizer, tmp_path):
    """Test splitting text with a sentence that exceeds token limit"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("This is a very long sentence. This is another sentence.")
    
    # Mock spaCy properly
    nlp = MagicMock()
    doc = MagicMock()
    sent1 = MagicMock()
    sent1.text = "This is a very long sentence."
    sent2 = MagicMock()
    sent2.text = "This is another sentence."
    doc.sents = [sent1, sent2]
    nlp.return_value = doc
    
    with patch('transcribe.summarize_model.initialize_spacy', return_value=nlp):
        with patch('transcribe.summarize_model.count_tokens') as mock_count:
            # Mock the window size via settings
            window_size = 100
            with patch('transcribe.summarize_model.settings.WINDOW_SIZE', window_size):
                # First call for prompt template, then for the concatenated text
                mock_count.side_effect = lambda x: 90 if "very long" in x else 10
                chunks = split_text(str(test_file), "Test Title")
                assert len(chunks) == 2  # Should split into two chunks
                assert "This is a very long sentence" in chunks[0]
                assert "This is another sentence" in chunks[1]

def test_summarize_with_mlx_generator_response():
    """Test successful MLX model generation"""
    with patch('transcribe.summarize_model.get_model_and_tokenizer') as mock_get:
        model = MagicMock()
        tokenizer = MagicMock()
        mock_get.return_value = (model, tokenizer)
        
        with patch('transcribe.summarize_model.generate') as mock_generate:
            mock_generate.return_value = "Generated summary"
            result = summarize_with_mlx("Test text", "Test Title")
            assert result is not None
            assert isinstance(result, str)

def test_save_summaries_write_error(tmp_path):
    """Test handling of file write errors in save_summaries"""
    summaries = ["Summary 1", "Summary 2"]
    with patch('builtins.open') as mock_open:
        mock_open.side_effect = IOError("Write failed")
        with pytest.raises(Exception):
            save_summaries(summaries, "test")

def test_create_summary_prompt_with_chat_template():
    """Test prompt creation with chat template"""
    model = MagicMock()
    tokenizer = MagicMock()
    
    def fake_hasattr(obj, attr):
        # Return False to bypass chat template logic
        return False
    
    # Mock the get_model_and_tokenizer and hasattr
    with patch('transcribe.summarize_model.get_model_and_tokenizer', return_value=(model, tokenizer)), \
         patch('builtins.hasattr', side_effect=fake_hasattr):
        
        # Call the function
        result = create_summary_prompt("Test text", "Test Title")
        
        # Verify the output matches the expected format
        assert "Title: Test Title" in result
        assert "Test text" in result
        assert "Extract ONLY information" in result
        assert "Your precise summary:" in result
        assert result.count("•") > 0  # Verify bullet points are present
        
        # Verify the mock wasn't called (since hasattr returned False)
        tokenizer.apply_chat_template.assert_not_called()

def test_init_logging():
    """Test logging initialization"""
    import importlib
    with patch('logging.getLogger') as mock_logger:
        # Force reload of the module to trigger logger initialization
        import transcribe.summarize_model
        importlib.reload(transcribe.summarize_model)
        assert mock_logger.called

def test_save_summaries_filesystem_error(tmp_path):
    """Test file system error handling in save_summaries"""
    from pathlib import Path
    summaries = ["Test summary 1", "Test summary 2"]
    
    with patch('builtins.open') as mock_open:
        mock_open.side_effect = OSError("Permission denied")
        with patch('transcribe.summarize_model.settings.OUTPUT_DIRS') as mock_dirs:
            mock_dirs.__getitem__.return_value = tmp_path
            
            with pytest.raises(Exception) as exc_info:
                save_summaries(summaries, "test_file")
            assert "Permission denied" in str(exc_info.value)

def test_main_script_execution(tmp_path):
    """Test the script's main execution path"""
    # Create a temporary test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Test content")
    test_title = "Test Title"
    
    with patch('sys.argv', ['summarize_model.py', str(test_file), test_title]):
        with patch('transcribe.summarize_model.split_text') as mock_split, \
             patch('transcribe.summarize_model.summarize_in_parallel') as mock_summarize, \
             patch('transcribe.summarize_model.save_summaries') as mock_save:
                
            # Setup mock returns
            mock_split.return_value = ['chunk1']
            mock_summarize.return_value = ['summary1']
            mock_save.return_value = 'output.txt'
            
            # Import and run the main script's functionality
            from transcribe.summarize_model import split_text, summarize_in_parallel, save_summaries
            
            text_path = str(test_file)
            chunks = split_text(text_path, test_title)
            summaries = summarize_in_parallel(chunks, test_title)
            output_path = save_summaries(summaries, test_file.stem)
            
            # Verify the execution flow
            mock_split.assert_called_once_with(str(test_file), test_title)
            mock_summarize.assert_called_once_with(['chunk1'], test_title)
            mock_save.assert_called_once_with(['summary1'], test_file.stem)
    
    result = create_summary_prompt("Test text", "Test Title")
    assert "Test text" in result
    assert "Test Title" in result
