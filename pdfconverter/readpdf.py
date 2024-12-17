import pyttsx3
import pymupdf


def readpdf(filename):
    reader_engine = pyttsx3.init()

    try:
        with open(f"media/{filename}.txt") as doc:
            text = doc.read()
        reader_engine.say(text)
        reader_engine.runAndWait()
    except FileNotFoundError:
        print(f"Error: File not found at 'MEDIA_ROOT/{filename}'.")




def convertpdf(filename):
    extracted_text = ""
    try:
        with pymupdf.open(f"media/{filename}.pdf") as doc:
            for page in doc:
                text = page.get_text()
                extracted_text += text  # Append text from each page
        return extracted_text  # Return the extracted text as a string
                
    except FileNotFoundError:
        print(f"Error: File not found at 'media/{filename}'.")



