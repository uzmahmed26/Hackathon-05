#!/usr/bin/env python3
"""
Validation script for the Customer Success AI test suite.
This script validates that all test files are properly structured and can be imported.
"""

import os
import sys
import importlib.util
from pathlib import Path

def validate_test_files():
    """Validate that all test files can be imported without errors."""
    test_dir = Path("tests")
    test_files = list(test_dir.glob("test_*.py"))
    
    print(f"Validating {len(test_files)} test files...")
    
    all_valid = True
    
    for test_file in test_files:
        print(f"\nValidating: {test_file.name}")
        try:
            # Import the module
            spec = importlib.util.spec_from_file_location(test_file.stem, test_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"  ✓ {test_file.name} - Valid")
        except ImportError as e:
            print(f"  ✗ {test_file.name} - Import Error: {e}")
            all_valid = False
        except SyntaxError as e:
            print(f"  ✗ {test_file.name} - Syntax Error: {e}")
            all_valid = False
        except Exception as e:
            print(f"  ✗ {test_file.name} - Error: {e}")
            all_valid = False
    
    return all_valid

def validate_agent_components():
    """Validate that agent components can be imported."""
    print("\nValidating agent components...")
    
    components = [
        ("agent.agent_prototype", "CustomerSuccessAgent"),
        ("agent.skills.knowledge_retrieval", "KnowledgeRetrieval"),
        ("agent.skills.sentiment_analysis", "SentimentAnalysis"),
        ("agent.skills.escalation_decision", "EscalationDecision"),
        ("agent.skills.channel_adaptation", "ChannelAdaptation"),
        ("agent.skills.customer_identification", "CustomerIdentification"),
    ]
    
    all_valid = True
    
    for module_path, class_name in components:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            print(f"  ✓ {module_path}.{class_name} - Available")
        except ImportError as e:
            print(f"  ✗ {module_path}.{class_name} - Import Error: {e}")
            all_valid = False
        except AttributeError as e:
            print(f"  ✗ {module_path}.{class_name} - Attribute Error: {e}")
            all_valid = False
        except Exception as e:
            print(f"  ✗ {module_path}.{class_name} - Error: {e}")
            all_valid = False
    
    return all_valid

def validate_channel_components():
    """Validate that channel components can be imported."""
    print("\nValidating channel components...")
    
    components = [
        ("channels.gmail_handler", "GmailHandler"),
        ("channels.whatsapp_handler", "WhatsAppHandler"),
        ("channels.web_form_handler", "WebFormHandler"),
    ]
    
    all_valid = True
    
    for module_path, class_name in components:
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            print(f"  ✓ {module_path}.{class_name} - Available")
        except ImportError as e:
            print(f"  ✗ {module_path}.{class_name} - Import Error: {e}")
            all_valid = False
        except AttributeError as e:
            print(f"  ✗ {module_path}.{class_name} - Attribute Error: {e}")
            all_valid = False
        except Exception as e:
            print(f"  ✗ {module_path}.{class_name} - Error: {e}")
            all_valid = False
    
    return all_valid

def validate_worker_components():
    """Validate that worker components can be imported."""
    print("\nValidating worker components...")
    
    try:
        # Import the worker module
        from workers.message_processor import UnifiedMessageProcessor
        print("  ✓ workers.message_processor.UnifiedMessageProcessor - Available")
        return True
    except ImportError as e:
        print(f"  ✗ workers.message_processor.UnifiedMessageProcessor - Import Error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ workers.message_processor.UnifiedMessageProcessor - Error: {e}")
        return False

def main():
    """Main validation function."""
    print("Customer Success AI - Test Suite Validation")
    print("=" * 50)
    
    # Change to the project directory
    os.chdir(Path(__file__).parent)
    
    # Validate test files
    test_valid = validate_test_files()
    
    # Validate agent components
    agent_valid = validate_agent_components()
    
    # Validate channel components
    channel_valid = validate_channel_components()
    
    # Validate worker components
    worker_valid = validate_worker_components()
    
    print("\n" + "=" * 50)
    print("VALIDATION SUMMARY:")
    print(f"Test Files: {'✓ PASS' if test_valid else '✗ FAIL'}")
    print(f"Agent Components: {'✓ PASS' if agent_valid else '✗ FAIL'}")
    print(f"Channel Components: {'✓ PASS' if channel_valid else '✗ FAIL'}")
    print(f"Worker Components: {'✓ PASS' if worker_valid else '✗ FAIL'}")
    
    overall_success = all([test_valid, agent_valid, channel_valid, worker_valid])
    print(f"\nOverall Status: {'✓ ALL VALID' if overall_success else '✗ SOME ISSUES FOUND'}")
    
    return overall_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)