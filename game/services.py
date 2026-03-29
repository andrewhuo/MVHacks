import os
import google.genai as genai

# Configure Gemini API
# (Temporary direct key storage for local testing only; replace with env var in production)
API_KEY = "AIzaSyDeZbXRD3wcPu3bRwCN5ZTWNQRCbM-X1DM"
if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    print("Warning: API_KEY is not set. Quiz functionality will not work.")
    client = None

def _select_supported_model() -> str | None:
    if not client:
        return None

    # Try list of models with generateContent in supported_methods
    # Prefer one directly from your model list; strip leading models/ if present.
    try:
        available = client.models.list()
        for m in available:
            if not getattr(m, 'name', None):
                continue
            nm = m.name
            if nm.startswith('models/'):
                nm = nm.replace('models/', '', 1)
            candidates = [nm]
            # keep an extra static list if the first model(s) fail.
            extra = ["gemini-1.0", "gemini-1.5", "gemini-2.0", "gemini-2.0-flash", "gemini-2.5-flash"]
            for candidate in candidates + extra:
                try:
                    client.models.generate_content(model=candidate, contents="Hello")
                    print(f"Selected model: {candidate}")
                    return candidate
                except Exception:
                    continue

    except Exception as e:
        print(f"Model list lookup failed: {e}")

    # Fallback known free-tier/commonly available options if list mode fails completely.
    fallback_candidates = ["gemini-1.0", "gemini-1.5", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-pro-latest"]
    for model in fallback_candidates:
        try:
            client.models.generate_content(model=model, contents="Hello")
            print(f"Fallback model works: {model}")
            return model
        except Exception:
            continue

    print("No valid Gemini model found for generateContent.")
    return None


def generate_ocean_cleanup_quiz(num_questions=5):
    """
    Generate quiz questions about cleaning trash from the ocean using Gemini API.

    Args:
        num_questions (int): Number of questions to generate

    Returns:
        list: List of dictionaries containing questions, options, and correct answers
    """
    if not client:
        return []

    model_name = _select_supported_model()
    if not model_name:
        print("Error generating quiz: no valid model available")
        return []

    prompt = f"""
    Generate {num_questions} multiple-choice questions about cleaning trash from the ocean and marine pollution.
    Each question should have 4 options (A, B, C, D) with one correct answer.

    Focus on topics like:
    - Ocean pollution sources
    - Environmental impact
    - Cleanup methods and technologies
    - Marine life protection
    - Sustainable practices

    Format each question as:
    Question: [question text]
    A) [option 1]
    B) [option 2]
    C) [option 3]
    D) [option 4]
    Correct: [letter]

    Separate questions with ---
    """

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        content = response.text

        # Parse the response
        questions = []
        sections = content.split('---')

        for section in sections:
            if 'Question:' in section and 'Correct:' in section:
                lines = section.strip().split('\n')
                question = ""
                options = []
                correct = ""

                for line in lines:
                    line = line.strip()
                    if line.startswith('Question:'):
                        question = line.replace('Question:', '').strip()
                    elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                        options.append(line[3:].strip())
                    elif line.startswith('Correct:'):
                        correct = line.replace('Correct:', '').strip().upper()

                if question and len(options) == 4 and correct:
                    questions.append({
                        'question': question,
                        'options': options,
                        'correct': correct
                    })

        return questions[:num_questions]  # Ensure we don't exceed requested number

    except Exception as e:
        print(f"Error generating quiz: {e}")
        return []

def display_quiz(questions):
    """
    Display quiz questions in a simple text format.
    
    Args:
        questions (list): List of question dictionaries
        
    Returns:
        str: Formatted quiz text
    """
    if not questions:
        return "No quiz questions available. Please check your GEMINI_API_KEY environment variable."
    
    quiz_text = "🌊 Ocean Cleanup Quiz 🌊\n\n"
    for i, q in enumerate(questions, 1):
        quiz_text += f"{i}. {q['question']}\n"
        for j, option in enumerate(q['options']):
            quiz_text += f"   {chr(65+j)}) {option}\n"
        quiz_text += f"   Correct Answer: {q['correct']}\n\n"
    
    return quiz_text