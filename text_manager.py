# text_manager.py
import yaml

def load_texts():
    try:
        with open('texts.yml', 'r', encoding='utf-8') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        print("Error: texts.yml not found. Please create the texts file.")
        return {}

texts = load_texts()

def get_text(key: str, **kwargs):
    """
    Returns the text for the given key, formatting it with any provided arguments.
    """
    return texts.get(key, f"Error: Text for key '{key}' not found.").format(**kwargs)