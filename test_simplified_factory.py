#!/usr/bin/env python3
"""
Test the simplified StrategyFactory usage with default strategy class.
"""

import sys
sys.path.append('/Users/jerzy/Develop/Python')

from MachineTrader import StrategyFactory, SingleStrategy

def test_simplified_factory():
    """Test the simplified factory usage"""
    
    print("🧪 Testing Simplified StrategyFactory Usage")
    print("=" * 50)
    
    # Test 1: Default strategy class
    print("\\n1. Testing default strategy class...")
    default_class = StrategyFactory.get_default_strategy()
    print(f"   Default strategy class: {default_class}")
    
    # Test 2: Simplified factory creation (no class name needed)
    print("\\n2. Testing simplified factory creation...")
    try:
        simplified_strategy = StrategyFactory.create(
            strategy_function="trade_zscore",
            symbol="TEST1",
            shares_per_trade=5,
            alpha=0.5
        )
        print(f"   ✅ Simplified creation successful: {simplified_strategy.strategy_name}")
        print(f"   Strategy type: {type(simplified_strategy).__name__}")
        print(f"   Symbol: {simplified_strategy.symbol}")
    except Exception as e:
        print(f"   ❌ Simplified creation failed: {e}")
    
    # Test 3: Explicit factory creation (with class name)
    print("\\n3. Testing explicit factory creation...")
    try:
        explicit_strategy = StrategyFactory.create("SingleStrategy",
            strategy_function="trade_momentum",
            symbol="TEST2",
            shares_per_trade=10,
            alpha=0.3
        )
        print(f"   ✅ Explicit creation successful: {explicit_strategy.strategy_name}")
        print(f"   Strategy type: {type(explicit_strategy).__name__}")
        print(f"   Symbol: {explicit_strategy.symbol}")
    except Exception as e:
        print(f"   ❌ Explicit creation failed: {e}")
    
    # Test 4: Verify both methods create same type
    print("\\n4. Testing type equivalence...")
    if 'simplified_strategy' in locals() and 'explicit_strategy' in locals():
        same_type = type(simplified_strategy) == type(explicit_strategy)
        print(f"   Both methods create same type: {same_type}")
        if same_type:
            print("   ✅ Type equivalence verified")
        else:
            print("   ❌ Type mismatch detected")
    
    # Test 5: Test setting different default
    print("\\n5. Testing default strategy management...")
    try:
        # Try to set an invalid default (should fail)
        StrategyFactory.set_default_strategy("NonExistentStrategy")
        print("   ❌ Should have failed to set invalid default")
    except ValueError as e:
        print(f"   ✅ Correctly prevented invalid default: {e}")
    
    # Confirm default is still correct
    current_default = StrategyFactory.get_default_strategy()
    print(f"   Current default after failed change: {current_default}")
    
    print("\\n✨ Simplified factory testing complete!")
    
    return simplified_strategy if 'simplified_strategy' in locals() else None

if __name__ == "__main__":
    try:
        strategy = test_simplified_factory()
        
        if strategy:
            print("\\n🎉 SUCCESS!")
            print("\\n💡 Key Benefits:")
            print("   • Can now use: StrategyFactory.create(strategy_function='trade_zscore', ...)")
            print("   • No need to specify 'CreateStrategy' class name")
            print("   • Backward compatible with explicit usage")
            print("   • More intuitive for common use cases")
            
        else:
            print("\\n❌ Test failed - strategy creation unsuccessful")
            
    except Exception as e:
        print(f"\\n💥 Test execution failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
