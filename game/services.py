import os
import google.genai as genai

# Configure Gemini API
API_KEY = "AIzaSyDeZbXRD3wcPu3bRwCN5ZTWNQRCbM-X1DM"
if API_KEY:
    client = genai.Client(api_key=API_KEY)
else:
    print("Warning: GEMINI_API_KEY environment variable not set. Quiz functionality will not work.")
    client = None

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
            model='gemini-2.0-flash-exp',
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