import os
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

endpoint = os.getenv("OPENAI_ENDPOINT")
api_key = os.getenv("OPENAI_API_KEY")
deployment_name = os.getenv("OPENAI_DEPLOYMENT_NAME")

print("=== TES KONEKSI AZURE OPENAI (VERSI DOCS) ===")
print(f"Endpoint: {endpoint}")
print(f"Deployment: {deployment_name}")
print("--------------------------------")

try:
    client = AzureOpenAI(
        api_version="2024-12-01-preview", 
        azure_endpoint=endpoint,
        api_key=api_key,
    )

    print("Menghubungi server Azure OpenAI... (Sedang berpikir)")
    
    response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "Anda adalah asisten AI. Jawablah dengan singkat.",
            },
            {
                "role": "user",
                "content": "Halo, tolong balas dengan teks: 'Koneksi AI berhasil 100%' jika kamu menerima pesan ini.",
            }
        ],
        model=deployment_name 
    )
    
    print("\n✅ KONEKSI BERHASIL!")
    print(f"🤖 Balasan AI: {response.choices[0].message.content}")

except Exception as e:
    print("\n❌ KONEKSI GAGAL!")
    print(f"Pesan Error: {e}")