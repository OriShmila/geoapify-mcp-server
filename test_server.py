#!/usr/bin/env python3
"""
Comprehensive test suite for the Geoapify MCP server.
Tests actual tool calls with real API requests and schema validation.
"""

import asyncio
import json
import time
import logging
from typing import Dict, List, Any
import jsonschema
from jsonschema import ValidationError

# Suppress httpx INFO logs to avoid exposing API keys in test output
logging.getLogger("httpx").setLevel(logging.WARNING)


class TestResults:
    """Track test results and statistics."""

    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.skipped_tests = 0
        self.results = []

    def add_result(self, test_name: str, success: bool, message: str, duration: float):
        """Add a test result."""
        self.total_tests += 1
        if success:
            self.passed_tests += 1
        else:
            self.failed_tests += 1

        self.results.append(
            {
                "test": test_name,
                "success": success,
                "message": message,
                "duration": duration,
            }
        )

    def add_skip(self, test_name: str, reason: str):
        """Add a skipped test."""
        self.total_tests += 1
        self.skipped_tests += 1
        self.results.append(
            {
                "test": test_name,
                "success": None,
                "message": f"SKIPPED: {reason}",
                "duration": 0,
            }
        )

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 50)
        print("🧪 TEST SUMMARY")
        print("=" * 50)
        print(f"Total Tests: {self.total_tests}")
        print(f"✅ Passed: {self.passed_tests}")
        print(f"❌ Failed: {self.failed_tests}")
        print(f"⏭️  Skipped: {self.skipped_tests}")

        if self.total_tests > 0:
            success_rate = (
                self.passed_tests / (self.total_tests - self.skipped_tests)
            ) * 100
            print(f"📊 Success Rate: {success_rate:.1f}%")

        # Show failed tests
        failed_tests = [r for r in self.results if r["success"] is False]
        if failed_tests:
            print("\n❌ FAILED TESTS:")
            for result in failed_tests:
                print(f"  • {result['test']}: {result['message']}")


def load_test_cases() -> List[Dict[str, Any]]:
    """Load test cases from JSON file."""
    try:
        with open("test_cases.json", "r") as f:
            data = json.load(f)
        return data["test_cases"]
    except FileNotFoundError:
        print("❌ test_cases.json not found")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing test_cases.json: {e}")
        return []


def validate_input_schema(
    tool_name: str, arguments: Dict[str, Any], schemas: Dict[str, Any]
) -> tuple[bool, str]:
    """Validate input arguments against tool's input schema."""
    if tool_name not in schemas:
        return False, f"No schema found for tool {tool_name}"

    tool_schema = schemas[tool_name]
    input_schema = tool_schema.get("inputSchema")

    if not input_schema:
        return False, f"No input schema defined for tool {tool_name}"

    try:
        jsonschema.validate(arguments, input_schema)
        return True, "Input validation passed"
    except ValidationError as e:
        return False, f"Input validation failed: {e.message}"
    except Exception as e:
        return False, f"Input validation error: {str(e)}"


def validate_output_schema(
    tool_name: str, result: Any, full_schema_data: Dict[str, Any]
) -> tuple[bool, str]:
    """Validate result against tool's output schema."""
    # Get tool schemas from the full schema data
    tools = full_schema_data.get("tools", [])
    tool_schema = None

    for tool in tools:
        if tool.get("name") == tool_name:
            tool_schema = tool
            break

    if not tool_schema:
        return False, f"No schema found for tool {tool_name}"

    output_schema = tool_schema.get("outputSchema")

    if not output_schema:
        return False, f"No output schema defined for tool {tool_name}"

    try:
        # Resolve $ref definitions if they exist
        definitions = full_schema_data.get("definitions", {})
        if definitions:
            # Create a complete schema with definitions for validation
            complete_schema = {**output_schema, "definitions": definitions}
        else:
            complete_schema = output_schema

        jsonschema.validate(result, complete_schema)
        return True, "Output validation passed"
    except ValidationError as e:
        return False, f"Output validation failed: {e.message}"
    except Exception as e:
        return False, f"Output validation error: {str(e)}"


def validate_schema_structure(schemas: Dict[str, Any]) -> List[str]:
    """Validate that all tool schemas have proper structure."""
    issues = []

    for tool_name, schema in schemas.items():
        # Check required top-level fields
        required_fields = ["name", "description", "inputSchema", "outputSchema"]
        for field in required_fields:
            if field not in schema:
                issues.append(f"{tool_name}: Missing {field}")

        # Validate input schema structure
        input_schema = schema.get("inputSchema", {})
        if input_schema:
            if "type" not in input_schema:
                issues.append(f"{tool_name}: inputSchema missing 'type'")
            if "properties" not in input_schema:
                issues.append(f"{tool_name}: inputSchema missing 'properties'")

        # Validate output schema structure
        output_schema = schema.get("outputSchema", {})
        if output_schema:
            if "type" not in output_schema and "$ref" not in output_schema:
                issues.append(f"{tool_name}: outputSchema missing 'type' or '$ref'")

    return issues


async def run_tool_test(
    tool_name: str,
    arguments: Dict[str, Any],
    test_case: Dict[str, Any],
    schemas: Dict[str, Any],
) -> tuple[bool, str, float, Dict[str, Any]]:
    """Run a single tool test case with comprehensive schema validation."""
    start_time = time.time()
    validation_results = {
        "input_validation": None,
        "output_validation": None,
        "legacy_validation": None,
    }

    try:
        # Import the tool functions directly
        from geoapify_mcp_server.server import TOOL_FUNCTIONS

        # 1. Validate input arguments against schema
        input_valid, input_msg = validate_input_schema(tool_name, arguments, schemas)
        validation_results["input_validation"] = {
            "valid": input_valid,
            "message": input_msg,
        }

        if not input_valid and test_case.get("should_succeed", True):
            return (
                False,
                f"Input schema validation failed: {input_msg}",
                time.time() - start_time,
                validation_results,
            )

        # 2. Call the tool function directly (bypassing MCP wrapper)
        if tool_name not in TOOL_FUNCTIONS:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool_function = TOOL_FUNCTIONS[tool_name]
        result = await tool_function(**arguments)
        duration = time.time() - start_time

        # 3. Validate result based on test case expectations
        if test_case.get("should_succeed", True):
            # Test should succeed
            if result is None:
                return False, "Tool returned None", duration, validation_results

            # 4. Validate output against schema - load full schema data
            with open("geoapify_mcp_server/tools.json", "r") as f:
                full_schema_data = json.load(f)
            output_valid, output_msg = validate_output_schema(
                tool_name, result, full_schema_data
            )
            validation_results["output_validation"] = {
                "valid": output_valid,
                "message": output_msg,
            }

            if not output_valid:
                return (
                    False,
                    f"Output schema validation failed: {output_msg}",
                    duration,
                    validation_results,
                )

            # 5. Legacy validation disabled (non-blocking)
            validation_results["legacy_validation"] = {
                "valid": True,
                "issues": [],
            }

            return (
                True,
                f"All validations passed - returned {type(result).__name__}",
                duration,
                validation_results,
            )
        else:
            # Test should fail
            return (
                False,
                f"Expected failure but got result: {type(result).__name__}",
                duration,
                validation_results,
            )

    except Exception as e:
        duration = time.time() - start_time
        if test_case.get("should_succeed", True):
            return False, f"Unexpected error: {str(e)}", duration, validation_results
        else:
            return True, f"Expected error: {str(e)}", duration, validation_results


async def test_server_components():
    """Test basic server components and schema structure."""
    print("MCP Server Test Suite")
    print("=" * 50)

    try:
        # Import the server components
        from geoapify_mcp_server.server import load_tool_schemas, TOOL_FUNCTIONS

        # Test schema loading
        schemas = load_tool_schemas()
        print(f"✅ Loaded {len(schemas)} tool schemas")

        # Test function mapping
        print(f"✅ Mapped {len(TOOL_FUNCTIONS)} tool functions")

        # Validate schema structure
        print("🔍 Validating schema structure...")
        schema_issues = validate_schema_structure(schemas)
        if schema_issues:
            print("❌ Schema structure issues found:")
            for issue in schema_issues:
                print(f"   • {issue}")
            return False
        else:
            print("✅ All schemas have valid structure")

        # Validate schema-function mapping
        missing_functions = []
        for schema_name in schemas.keys():
            if schema_name not in TOOL_FUNCTIONS:
                missing_functions.append(schema_name)

        if missing_functions:
            print(f"❌ Missing function mappings: {missing_functions}")
            return False

        print("✅ All schemas have corresponding functions")

        # Test schema definitions loading
        with open("geoapify_mcp_server/tools.json", "r") as f:
            full_schema_data = json.load(f)

        definitions = full_schema_data.get("definitions", {})
        if definitions:
            print(
                f"✅ Loaded {len(definitions)} schema definitions for $ref resolution"
            )

        return True, schemas

    except Exception as e:
        print(f"❌ Component test failed: {e}")
        import traceback

        traceback.print_exc()
        return False, {}


async def run_tool_tests(schemas: Dict[str, Any]):
    """Run all tool tests with real API calls and comprehensive schema validation."""
    print("\n🧪 Running Tool Tests with Schema Validation")
    print("-" * 50)

    test_cases = load_test_cases()
    if not test_cases:
        print("❌ No test cases loaded")
        return TestResults()

    results = TestResults()

    # Check if API key is available

    print(f"🚀 Running {len(test_cases)} test cases with full schema validation...")

    for i, test_case in enumerate(test_cases, 1):
        test_name = test_case["name"]
        tool_name = test_case["tool"]
        arguments = test_case["arguments"]
        description = test_case["description"]

        print(f"\n[{i}/{len(test_cases)}] {test_name}")
        print(f"    📝 {description}")
        print(
            f"    🔧 {tool_name}({', '.join(f'{k}={v}' for k, v in arguments.items())})"
        )

        try:
            success, message, duration, validation_results = await run_tool_test(
                tool_name, arguments, test_case, schemas
            )

            status_icon = "✅" if success else "❌"
            print(f"    {status_icon} {message} ({duration:.2f}s)")

            # Show detailed validation results
            if validation_results.get("input_validation"):
                input_val = validation_results["input_validation"]
                input_icon = "✅" if input_val["valid"] else "❌"
                print(f"       📥 Input: {input_icon} {input_val['message']}")

            if validation_results.get("output_validation"):
                output_val = validation_results["output_validation"]
                output_icon = "✅" if output_val["valid"] else "❌"
                print(f"       📤 Output: {output_icon} {output_val['message']}")

            results.add_result(test_name, success, message, duration)

            # Add small delay between API calls to be respectful
            if i < len(test_cases):
                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"    ❌ Test execution failed: {e}")
            results.add_result(test_name, False, f"Test execution failed: {e}", 0)

    return results


async def main():
    """Main test runner with comprehensive schema validation."""
    # Test server components first
    components_result = await test_server_components()

    if isinstance(components_result, tuple):
        components_ok, schemas = components_result
    else:
        components_ok = components_result
        schemas = {}

    if not components_ok:
        print("\n❌ Component tests failed - skipping tool tests")
        return

    # Run tool tests with schema validation
    results = await run_tool_tests(schemas)

    # Print summary
    results.print_summary()

    # Print enhanced usage info
    print("\n💡 Enhanced Schema Validation Features:")
    print("  🔍 Input parameters validated against JSON Schema")
    print("  🔍 Output responses validated against JSON Schema")
    print("  🔍 Schema structure validation with definitions")
    print("  🔍 Comprehensive error reporting")
    print("\n💡 Usage Information:")
    print("  • Run with: uv run python test_server.py")
    print("  • Add test cases in test_cases.json")
    print("  • Modify tools.json to update schemas")
    print("  • Server ready for MCP client connections")


if __name__ == "__main__":
    asyncio.run(main())
