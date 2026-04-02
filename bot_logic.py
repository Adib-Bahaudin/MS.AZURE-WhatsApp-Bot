import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AzureOpenAI(
    api_version="2024-12-01-preview",
    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

def get_ai_response(user_text: str, sender_number: str) -> str:
    """Fungsi utama untuk memproses chat dan mendapatkan balasan AI."""
    
    deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")
    
    try:
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Anda adalah asisten virtual kasir toko yang ramah, sopan, dan pintar. Jawablah pertanyaan dengan singkat dan jelas."
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ],
            model=deployment_name, 
            max_tokens=250,        
            temperature=0.7        
        )
        
        return response.choices[0].message.content

    except Exception as e:
        print(f"❌ Error pada Azure OpenAI: {e}")
        return "Mohon maaf kak, sistem asisten kami sedang beristirahat sejenak. Silakan coba beberapa saat lagi ya 🙏"