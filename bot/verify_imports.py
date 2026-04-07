#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

try:
    from bot import HomeworkGraderBot, TELEGRAM_TOKEN, BACKEND_URL
    print('✓ Bot imports successful')
    print(f'  TELEGRAM_TOKEN: {"set" if TELEGRAM_TOKEN else "not set"}')
    print(f'  BACKEND_URL: {BACKEND_URL}')
    print(f'  Bot class methods: start, handle_photo, analyze_homework, format_result')
except Exception as e:
    print(f'✗ Import failed: {e}')
    sys.exit(1)
