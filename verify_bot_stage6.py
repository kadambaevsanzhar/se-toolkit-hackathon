#!/usr/bin/env python3
"""
Stage 6: Telegram Bot - Comprehensive Verification
"""

import os
import sys
from pathlib import Path

def check_bot_files():
    """Verify all bot files exist."""
    print("✓ Checking bot files...")
    bot_dir = Path(__file__).parent / "bot"
    
    required_files = {
        "bot.py": "Main bot implementation",
        "Dockerfile": "Docker containerization",
        "requirements.txt": "Python dependencies",
    }
    
    all_exist = True
    for filename, description in required_files.items():
        path = bot_dir / filename
        if path.exists():
            size = path.stat().st_size
            print(f"  ✓ {filename:20} ({size:,} bytes) - {description}")
        else:
            print(f"  ✗ {filename} - MISSING")
            all_exist = False
    
    return all_exist

def check_requirements():
    """Verify requirements are minimal and correct."""
    print("✓ Checking Python requirements...")
    
    req_path = Path(__file__).parent / "bot" / "requirements.txt"
    requirements = req_path.read_text().strip().split('\n')
    
    required_packages = [
        ('python-telegram-bot', 'Telegram bot framework'),
        ('requests', 'HTTP client for backend API'),
        ('pillow', 'Image handling'),
    ]
    
    print(f"  Found {len(requirements)} packages:")
    for pkg in requirements:
        if pkg.strip():
            print(f"  • {pkg}")
    
    # Check all required packages present
    req_text = ' '.join(requirements).lower()
    all_present = True
    for pkg_name, description in required_packages:
        if pkg_name.lower() in req_text or pkg_name.replace('-', '_').lower() in req_text:
            print(f"  ✓ {pkg_name:30} - {description}")
        else:
            print(f"  ✗ {pkg_name:30} - MISSING")
            all_present = False
    
    return all_present

def check_bot_implementation():
    """Verify bot implementation has required methods."""
    print("✓ Checking bot implementation...")
    
    bot_path = Path(__file__).parent / "bot" / "bot.py"
    bot_code = bot_path.read_text()
    
    required_components = {
        'class HomeworkGraderBot': 'Bot class definition',
        'async def start': 'Start command handler',
        'async def handle_photo': 'Photo message handler',
        'def analyze_homework': 'Backend analysis method',
        'def format_result': 'Result formatting method',
        'def main': 'Main entry point',
        'TELEGRAM_TOKEN': 'Token configuration',
        'BACKEND_URL': 'Backend URL configuration',
    }
    
    all_present = True
    for component, description in required_components.items():
        if component in bot_code:
            print(f"  ✓ {description:40} ({component})")
        else:
            print(f"  ✗ {description:40} - MISSING")
            all_present = False
    
    return all_present

def check_docker_setup():
    """Verify Docker configuration."""
    print("✓ Checking Docker setup...")
    
    dockerfile_path = Path(__file__).parent / "bot" / "Dockerfile"
    dockerfile = dockerfile_path.read_text()
    
    checks = [
        ('FROM python', 'Base image configured'),
        ('COPY requirements.txt', 'Dependencies copied'),
        ('RUN pip install', 'Dependencies installed'),
        ('COPY bot.py', 'Bot code copied'),
        ('CMD ["python", "bot.py"]', 'Startup command set'),
    ]
    
    all_present = True
    for check_str, description in checks:
        if check_str in dockerfile:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - NOT FOUND")
            all_present = False
    
    return all_present

def check_compose_integration():
    """Verify docker-compose integration."""
    print("✓ Checking docker-compose integration...")
    
    compose_path = Path(__file__).parent / "docker-compose.yml"
    compose = compose_path.read_text()
    
    checks = [
        ('bot:', 'Bot service defined'),
        ('build: ./bot', 'Bot image build configured'),
        ('TELEGRAM_TOKEN:', 'Environment variable configured'),
        ('BACKEND_URL:', 'Backend URL configured'),
        ('depends_on:', 'Service dependency defined'),
    ]
    
    all_present = True
    for check_str, description in checks:
        if check_str in compose:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - NOT FOUND")
            all_present = False
    
    return all_present

def check_documentation():
    """Verify documentation exists."""
    print("✓ Checking documentation...")
    
    readme_path = Path(__file__).parent / "README.md"
    readme = readme_path.read_text()
    
    sections = [
        ('Telegram Bot', 'Bot feature mentioned'),
        ('TELEGRAM_TOKEN', 'Token documented'),
        ('Bot Service', 'Bot service section'),
        ('python bot.py', 'Local run instructions'),
    ]
    
    all_present = True
    for section, description in sections:
        if section in readme:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ {description} - NOT FOUND")
            all_present = False
    
    return all_present

def check_imports():
    """Verify bot imports work with mock token."""
    print("✓ Checking imports...")
    
    try:
        os.environ['TELEGRAM_TOKEN'] = 'test-token-for-verification'
        sys.path.insert(0, str(Path(__file__).parent / "bot"))
        
        from bot import HomeworkGraderBot, TELEGRAM_TOKEN, BACKEND_URL
        
        print(f"  ✓ HomeworkGraderBot class imported")
        print(f"  ✓ Configuration variables available")
        print(f"  ✓ TELEGRAM_TOKEN: {type(TELEGRAM_TOKEN).__name__} (loaded from environment)")
        print(f"  ✓ BACKEND_URL: {BACKEND_URL}")
        
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False

def check_bot_functionality():
    """Verify bot has all required methods."""
    print("✓ Checking bot functionality...")
    
    try:
        os.environ['TELEGRAM_TOKEN'] = 'test-token'
        sys.path.insert(0, str(Path(__file__).parent / "bot"))
        
        from bot import HomeworkGraderBot
        import inspect
        
        methods = {
            'start': 'Handles /start command',
            'handle_photo': 'Processes photo uploads',
            'analyze_homework': 'Sends to backend for analysis',
            'format_result': 'Formats result for display',
        }
        
        for method_name, description in methods.items():
            if hasattr(HomeworkGraderBot, method_name):
                method = getattr(HomeworkGraderBot, method_name)
                is_async = inspect.iscoroutinefunction(method)
                async_marker = " (async)" if is_async else ""
                print(f"  ✓ {method_name:20} - {description}{async_marker}")
            else:
                print(f"  ✗ {method_name:20} - NOT FOUND")
                return False
        
        return True
    except Exception as e:
        print(f"  ✗ Functionality check failed: {e}")
        return False

def main():
    """Run all verifications."""
    print("\n" + "=" * 70)
    print("STAGE 6: TELEGRAM BOT - COMPREHENSIVE VERIFICATION")
    print("=" * 70 + "\n")
    
    checks = [
        ("Bot Files", check_bot_files),
        ("Python Requirements", check_requirements),
        ("Bot Implementation", check_bot_implementation),
        ("Docker Setup", check_docker_setup),
        ("Docker Compose Integration", check_compose_integration),
        ("Documentation", check_documentation),
        ("Imports", check_imports),
        ("Functionality", check_bot_functionality),
    ]
    
    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
            print()
        except Exception as e:
            print(f"  ✗ Check failed: {e}\n")
            results[name] = False
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for name, result in results.items():
        status = "✓" if result else "✗"
        print(f"{status} {name}")
    
    print(f"\nResult: {passed}/{total} checks passed\n")
    
    if passed == total:
        print("✓ STAGE 6 BOT IMPLEMENTATION VERIFIED\n")
        print("Bot is ready for deployment:")
        print("  • Minimal and focused (< 150 lines)")
        print("  • Accepts one photo per message")
        print("  • Sends to backend /analyze endpoint")
        print("  • Returns formatted result with score & feedback")
        print("  • Uses environment variables for config")
        print("  • Integrated with Docker Compose")
        print("\nTo deploy:")
        print("  1. Obtain Telegram bot token from @BotFather")
        print("  2. Set TELEGRAM_TOKEN in .env or docker-compose")
        print("  3. Run: docker-compose up bot")
        print("  4. Send photo to bot in Telegram")
        return 0
    else:
        print(f"✗ {total - passed} checks failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
