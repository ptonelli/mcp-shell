#!/usr/bin/env python3
"""
Test case to demonstrate the replace_lines bug
"""
import tempfile
import os
from unittest.mock import MagicMock
from server import replace_lines, WORKDIR

def test_replace_single_line_bug():
    """Test that demonstrates the replace_lines bug when end_line is None"""
    
    # Create a mock context
    ctx = MagicMock()
    ctx.request_context = None
    ctx.session_id = None
    
    # Create test content
    original_content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""
    
    expected_after_replace = """Line 1
Line 2
REPLACED LINE 3
Line 4
Line 5
"""
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=WORKDIR, delete=False) as f:
        f.write(original_content)
        temp_file = f.name
    
    try:
        # Get just the filename relative to WORKDIR
        rel_path = os.path.relpath(temp_file, WORKDIR)
        
        print("=== BEFORE REPLACE ===")
        with open(temp_file, 'r') as f:
            before_content = f.read()
            print(repr(before_content))
        
        # Try to replace line 3 (should replace "Line 3" with "REPLACED LINE 3")
        result = replace_lines(
            ctx=ctx,
            file_path=rel_path,
            start_line=3,  # Replace line 3
            new_content="REPLACED LINE 3"
            # end_line is None by default
        )
        
        print("=== REPLACE RESULT ===")
        print(f"Success: {result.get('success')}")
        print(f"Diff:\n{result.get('diff', 'No diff')}")
        
        print("=== AFTER REPLACE ===")
        with open(temp_file, 'r') as f:
            after_content = f.read()
            print(repr(after_content))
        
        print("=== EXPECTED ===")
        print(repr(expected_after_replace))
        
        # Check if the result is what we expect
        print("=== ANALYSIS ===")
        if after_content == expected_after_replace:
            print("✅ SUCCESS: Line was replaced correctly")
            return True
        else:
            print("❌ BUG DETECTED: Line was not replaced correctly")
            print(f"Expected:\n{expected_after_replace}")
            print(f"Got:\n{after_content}")
            
            # Count lines to analyze the problem
            after_lines = after_content.splitlines()
            expected_lines = expected_after_replace.splitlines()
            print(f"Expected {len(expected_lines)} lines, got {len(after_lines)} lines")
            
            return False
            
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

if __name__ == "__main__":
    print("Testing replace_lines function...")
    success = test_replace_single_line_bug()
    if success:
        print("\n🎉 Test PASSED - No bug detected")
    else:
        print("\n🐛 Test FAILED - Bug confirmed")
