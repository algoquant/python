#!/usr/bin/env python3
"""
Test script for indicator_name argument parsing
"""
import argparse
import sys
import os

# Add MachineTrader to path to import GetArgs
sys.path.append(os.path.join(os.path.dirname(__file__), 'MachineTrader'))

def create_test_parser():
    """Create a test parser with just the indicator_name argument"""
    parser = argparse.ArgumentParser(description='Test indicator_name argument')
    parser.add_argument('--indicator_name', 
                       default='calc_zscore', 
                       help='Name of the technical indicator to use (default: calc_zscore)')
    return parser

def test_indicator_name():
    """Test the indicator_name argument parsing"""
    parser = create_test_parser()
    
    # Test with default value
    print("Testing with default value:")
    args = parser.parse_args([])
    print(f"  indicator_name: {args.indicator_name}")
    
    # Test with explicit value
    print("\nTesting with explicit value:")
    args = parser.parse_args(['--indicator_name', 'calc_zscorew'])
    print(f"  indicator_name: {args.indicator_name}")
    
    # Test with another value
    print("\nTesting with another value:")
    args = parser.parse_args(['--indicator_name', 'calc_ema'])
    print(f"  indicator_name: {args.indicator_name}")

if __name__ == '__main__':
    test_indicator_name()
