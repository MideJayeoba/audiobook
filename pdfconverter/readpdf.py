import pyttsx3
import pymupdf


def convertpdf(filename):
    extracted_text = ""
    try:
        with pymupdf.open(f"media/{filename}.pdf") as doc:
            with open(f"media/{filename}.txt", "w") as extracted:
                for page in doc:
                    text = page.get_text()
                    extracted_text += text
                    extracted.write(text)
        return extracted_text  # Return the extracted text as a string
                
    except FileNotFoundError:
        print(f"Error: File not found at 'media/{filename}'.")
    except UnicodeEncodeError:
        pass

    


def readpdf(filename):
    reader_engine = pyttsx3.init()

    try:
        with open(f"media/{filename}.txt",) as doc:
            text = doc.read()
        reader_engine.say(text)
        reader_engine.runAndWait()
    except FileNotFoundError:
        print(f"Error: File not found at 'media/")



