import os
from groq import Groq

def fetch_salary_from_groq(job_title: str, location: str = "global") -> str:
    """
    Ask Groq AI for an estimated salary range for a given job and location.
    Returns a clean string like '$70,000 - $120,000'
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "N/A"
        
    client = Groq(api_key=api_key)
    
    prompt = (
        f"Provide a realistic yearly salary range in USD "
        f"for a {job_title} in {location} with mid-level experience. "
        f"Return ONLY the range like '$70,000 - $120,000'."
    )
    
    try:
        chat = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return chat.choices[0].message.content.strip()
    except Exception:
        return "N/A"

def fetch_profession_description_from_groq(job_title: str) -> str:
    """
    Ask Groq AI for a brief description of a profession.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return ""
        
    client = Groq(api_key=api_key)
    
    prompt = (
        f"Provide a professional, detailed, and engaging description of what a {job_title} does. "
        f"Explain the core responsibilities, the impact they have on a business, and the primary tools or methodologies they use. "
        f"Keep it between 3-5 sentences. No introductory text like 'Here is a description', just the content."
    )
    
    try:
        chat = client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return chat.choices[0].message.content.strip()
    except Exception:
        return ""
