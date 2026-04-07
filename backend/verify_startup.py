from main import app, ai_service
print('✓ Backend imported successfully')
print(f'  AI Service: model={ai_service.model}')
print(f'  AI_BASE_URL={ai_service.base_url}')
print(f'  API_KEY {"set" if ai_service.api_key else "not set"}')
