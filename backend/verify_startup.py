from main import app
from ai.analyzer.openai_analyzer import analyzer_service
from ai.validator.openai_validator import ollama_validator
print('✓ Backend imported successfully')
print(f'  Analyzer model={analyzer_service.model}')
print(f'  Validator model={ollama_validator.model}')
print(f'  OpenAI key {"set" if analyzer_service.client.api_key else "not set"}')
