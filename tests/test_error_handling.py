"""
Tests for error handling and circuit breaker functionality.
"""

import time
import unittest
from unittest.mock import MagicMock

from src.infinite_memory_mcp.mcp.mcp_server import CircuitBreaker, MCPServer


class TestCircuitBreaker(unittest.TestCase):
    """Test cases for circuit breaker pattern."""
    
    def setUp(self):
        """Set up test cases."""
        self.circuit_breaker = CircuitBreaker(failure_threshold=2, reset_timeout=1)
    
    def test_circuit_initially_closed(self):
        """Test that the circuit is initially closed (allowing requests)."""
        self.assertFalse(self.circuit_breaker.is_open("test_command"))
    
    def test_circuit_opens_after_failures(self):
        """Test that the circuit opens after reaching the failure threshold."""
        # Record failures
        self.circuit_breaker.record_failure("test_command")
        # Circuit should still be closed
        self.assertFalse(self.circuit_breaker.is_open("test_command"))
        
        # Record another failure
        self.circuit_breaker.record_failure("test_command")
        # Circuit should now be open
        self.assertTrue(self.circuit_breaker.is_open("test_command"))
    
    def test_circuit_resets_after_timeout(self):
        """Test that the circuit resets after the timeout period."""
        # Open the circuit
        self.circuit_breaker.record_failure("test_command")
        self.circuit_breaker.record_failure("test_command")
        self.assertTrue(self.circuit_breaker.is_open("test_command"))
        
        # Set an artificially old last failure time
        self.circuit_breaker.last_failure_time["test_command"] = time.time() - 2
        
        # Circuit should now be closed due to timeout
        self.assertFalse(self.circuit_breaker.is_open("test_command"))
    
    def test_success_resets_failure_count(self):
        """Test that a success resets the failure count."""
        # Record a failure
        self.circuit_breaker.record_failure("test_command")
        self.assertEqual(self.circuit_breaker.failure_count["test_command"], 1)
        
        # Record a success
        self.circuit_breaker.record_success("test_command")
        self.assertEqual(self.circuit_breaker.failure_count["test_command"], 0)
    
    def test_independent_commands(self):
        """Test that circuit breaker is independent for different commands."""
        # Record failures for one command
        self.circuit_breaker.record_failure("command1")
        self.circuit_breaker.record_failure("command1")
        self.assertTrue(self.circuit_breaker.is_open("command1"))
        
        # Another command should still be allowed
        self.assertFalse(self.circuit_breaker.is_open("command2"))


class TestMCPServerErrorHandling(unittest.TestCase):
    """Test cases for MCP server error handling."""
    
    def setUp(self):
        """Set up test cases."""
        self.server = MCPServer()
        # Register test command handlers
        self.successful_handler = MagicMock(return_value={"status": "OK"})
        self.failing_handler = MagicMock(side_effect=Exception("Test error"))
        self.server.register_command("test_success", self.successful_handler)
        self.server.register_command("test_failure", self.failing_handler)
        # Reduce retry delay for faster tests
        self.server.retry_delay = 0.01
    
    def test_successful_command(self):
        """Test processing a successful command."""
        result = self.server.process_request('{"action": "test_success", "data": "test"}')
        self.assertEqual(result, {"status": "OK"})
        self.assertEqual(self.server.error_count, 0)
    
    def test_command_with_retry(self):
        """Test command retry logic on failure."""
        # Make the handler fail twice then succeed
        side_effects = [
            Exception("Retry 1"),
            Exception("Retry 2"),
            {"status": "OK"}
        ]
        test_handler = MagicMock(side_effect=side_effects)
        self.server.register_command("test_retry", test_handler)
        
        result = self.server.process_request('{"action": "test_retry", "data": "test"}')
        self.assertEqual(result, {"status": "OK"})
        self.assertEqual(test_handler.call_count, 3)
    
    def test_command_fails_after_retries(self):
        """Test that a command fails after all retries are exhausted."""
        result = self.server.process_request('{"action": "test_failure", "data": "test"}')
        self.assertEqual(result["status"], "error")
        self.assertIn("Command failed after", result["error"])
        self.assertEqual(self.failing_handler.call_count, self.server.max_retry_attempts)
    
    def test_unknown_command(self):
        """Test processing an unknown command."""
        result = self.server.process_request('{"action": "unknown_command", "data": "test"}')
        self.assertEqual(result["status"], "error")
        self.assertIn("Unknown action", result["error"])
    
    def test_invalid_json(self):
        """Test processing invalid JSON."""
        result = self.server.process_request('{"invalid json}')
        self.assertEqual(result["status"], "error")
        self.assertIn("Invalid JSON", result["error"])
    
    def test_missing_action(self):
        """Test processing a request with missing action."""
        result = self.server.process_request('{"data": "test"}')
        self.assertEqual(result["status"], "error")
        self.assertIn("Missing 'action'", result["error"])
    
    def test_circuit_breaker_integration(self):
        """Test circuit breaker integration with command processing."""
        # Reduce the failure threshold for testing
        self.server.circuit_breaker.failure_threshold = 2
        
        # First attempt - will fail but circuit stays closed
        result1 = self.server.process_request('{"action": "test_failure", "data": "test1"}')
        self.assertEqual(result1["status"], "error")
        
        # Second attempt - will fail and open the circuit
        result2 = self.server.process_request('{"action": "test_failure", "data": "test2"}')
        self.assertEqual(result2["status"], "error")
        
        # Third attempt - circuit is open, so handler shouldn't be called
        result3 = self.server.process_request('{"action": "test_failure", "data": "test3"}')
        self.assertEqual(result3["status"], "error")
        self.assertIn("Service temporarily unavailable", result3["error"])
        
        # Verify the handler was only called twice (not on the third attempt)
        self.assertEqual(self.failing_handler.call_count, 2 * self.server.max_retry_attempts)
    
    def test_health_check(self):
        """Test the health check functionality."""
        # Process a failing command a few times to degrade health
        for _ in range(3):
            self.server.process_request('{"action": "test_failure", "data": "test"}')
        
        # Check health status
        health = self.server.get_health()
        self.assertEqual(health["status"], "degraded")
        self.assertGreater(health["error_count"], 0)
        self.assertIsNotNone(health["last_error"])


if __name__ == "__main__":
    unittest.main() 