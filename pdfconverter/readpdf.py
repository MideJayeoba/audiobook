"""
PDF text extraction and text-to-speech conversion utilities.

This module provides functions for extracting text from PDF files using
PyMuPDF and generating spoken-word MP3 audio files using gTTS (Google
Text-to-Speech).
"""
import os

import pymupdf
from gtts import gTTS


def convertpdf(filepath):
    """
    Extract all text content from a PDF file using PyMuPDF.

    Iterates over every page in the document and concatenates the text
    returned by each page's ``get_text()`` method.

    Args:
        filepath (str): Absolute path to the PDF file on disk.

    Returns:
        str: The complete extracted text from the PDF.

    Raises:
        FileNotFoundError: If ``filepath`` does not exist.
        RuntimeError: If PyMuPDF encounters an error reading the document.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    extracted_text = ""
    try:
        with pymupdf.open(filepath) as doc:
            for page in doc:
                extracted_text += page.get_text()
    except Exception as exc:
        raise RuntimeError(f"Error reading PDF '{filepath}': {exc}") from exc

    return extracted_text


def generate_audio(text, output_path):
    """
    Convert a text string to an MP3 audio file using gTTS.

    The parent directory of ``output_path`` is created automatically if it
    does not already exist.

    Args:
        text (str): The text to be converted to speech.
        output_path (str): Absolute path where the MP3 file should be saved.

    Raises:
        ValueError: If ``text`` is empty or contains only whitespace.
        RuntimeError: If gTTS fails to generate the audio file.
    """
    if not text or not text.strip():
        raise ValueError("Cannot generate audio from empty text.")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(output_path)
    except Exception as exc:
        raise RuntimeError(f"Error generating audio file: {exc}") from exc

