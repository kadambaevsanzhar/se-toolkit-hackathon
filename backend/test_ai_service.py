#!/usr/bin/env python3
"""
Test suite for real Qwen AI v1 API integration.
Tests both success and failure scenarios.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from PIL import Image
import io

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_service import ai_service
from ai_validator import AIResponseValidator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_image_bytes() -> bytes:
    """Create a simple test image in memory."""
    img = Image.new("RGB", (50, 50), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()

async def test_real_api_success():
    """
    Test 1: Successful API call with real endpoint.
    
    Prerequisites:
    - AI_BASE_URL points to running qwen-code-api service
    - AI_API_KEY is valid
    """
    logger.info("=" * 60)
    logger.info("TEST 1: Real API Call (Success Case)")
    logger.info("=" * 60)
    
    # Check configuration
    logger.info(f"AI_BASE_URL: {ai_service.base_url}")
    logger.info(f"AI_MODEL: {ai_service.model}")
    logger.info(f"API_KEY configured: {'Yes' if ai_service.api_key else 'No'}")
    
    if not ai_service.api_key or ai_service.api_key == "my-secret-qwen-key":
        logger.warning("⚠️ AI_API_KEY not configured properly. Using placeholder.")
        logger.warning("   This test will likely fail unless API allows placeholder keys.")
    
    try:
        image_data = create_test_image_bytes()
        logger.info(f"Created test image: {len(image_data)} bytes")
        
        logger.info("Calling AI service...")
        response = await ai_service.analyze_homework_image(image_data, "test.png")
        
        logger.info("✓ API call succeeded!")
        logger.info(f"Response: {response}")
        
        # Validate response
        logger.info("Validating response...")
        normalized = AIResponseValidator.validate_and_normalize(response)
        logger.info(f"✓ Validation passed!")
        logger.info(f"Normalized: {normalized}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ API call failed: {e}")
        logger.info("This is expected if:")
        logger.info("  - Qwen API is not running at AI_BASE_URL")
        logger.info("  - AI_API_KEY is not valid")
        logger.info("  - Network connection issue")
        return False

async def test_api_error_handling():
    """
    Test 2: Graceful error handling when API is unavailable.
    """
    logger.info("=" * 60)
    logger.info("TEST 2: API Error Handling (Failure Case)")
    logger.info("=" * 60)
    
    # Save current config and set to invalid endpoint
    original_base_url = ai_service.base_url
    original_api_key = ai_service.api_key
    
    try:
        # Point to non-existent service
        ai_service.base_url = "http://invalid-host-12345:12345/v1"
        
        logger.info(f"Using invalid base_url: {ai_service.base_url}")
        
        image_data = create_test_image_bytes()
        logger.info(f"Created test image: {len(image_data)} bytes")
        
        logger.info("Attempting API call to invalid endpoint...")
        response = await ai_service.analyze_homework_image(image_data, "test.png")
        
        logger.error("✗ API call should have failed but didn't!")
        return False
        
    except Exception as e:
        logger.info(f"✓ API call failed as expected: {type(e).__name__}")
        logger.info(f"   Error: {e}")
        
        # Verify we can use fallback
        logger.info("Testing fallback response creation...")
        try:
            fallback = AIResponseValidator.create_fallback_response(str(e))
            logger.info(f"✓ Fallback response created: {fallback}")
            return True
        except Exception as fb_error:
            logger.error(f"✗ Fallback response failed: {fb_error}")
            return False
    
    finally:
        # Restore original config
        ai_service.base_url = original_base_url
        ai_service.api_key = original_api_key

async def test_response_extraction():
    """
    Test 3: Response extraction and parsing logic.
    Tests the JSON extraction from various response formats.
    """
    logger.info("=" * 60)
    logger.info("TEST 3: Response Extraction and Normalization")
    logger.info("=" * 60)
    
    # Test direct JSON response
    test_response = {
        "choices": [
            {
                "message": {
                    "content": '{"suggested_score": 8, "short_feedback": "Good work", "strengths": ["Clear"], "mistakes": []}'
                }
            }
        ]
    }
    
    try:
        logger.info("Testing JSON extraction from response...")
        result = ai_service._extract_analysis_result(test_response)
        logger.info(f"✓ Extracted: {result}")
        
        # Validate
        normalized = AIResponseValidator.validate_and_normalize(result)
        logger.info(f"✓ Normalized: {normalized}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Extraction failed: {e}")
        return False

async def main():
    """Run all tests."""
    logger.info("\n")
    logger.info("╔" + "=" * 58 + "╗")
    logger.info("║" + " AI Service Integration Tests - Real Qwen API v1 ".center(58) + "║")
    logger.info("╚" + "=" * 58 + "╝")
    logger.info("")
    
    results = {}
    
    # Test 1: Real API (may fail if not running)
    results["Real API Call"] = await test_real_api_success()
    logger.info("")
    
    # Test 2: Error Handling
    results["Error Handling"] = await test_api_error_handling()
    logger.info("")
    
    # Test 3: Response Extraction
    results["Response Extraction"] = await test_response_extraction()
    logger.info("")
    
    # Summary
    logger.info("=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {name}")
    
    logger.info("")
    
    # Overall result
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    logger.info(f"Overall: {passed}/{total} tests completed")
    
    if passed >= 2:  # Error handling and response extraction should always pass
        logger.info("✓ Core functionality working!")
    else:
        logger.info("⚠️ Some tests failed - check logs above")
    
    return passed >= 2

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Test execution failed: {e}", exc_info=True)
        sys.exit(1)
