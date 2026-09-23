"""
Unit tests for ModelProvider factory fail-closed behavior (WS3, SEC-01).

Test coverage:
 1. get_provider("groq", api_key="") raises ConfigurationError
 2. get_provider("groq", api_key="sk-test") returns GroqProvider
 3. get_provider("openai", api_key="") raises ConfigurationError
 4. get_provider("openai", api_key="sk-test") returns OpenAIProvider
 5. get_provider("mock") in development returns MockProvider
 6. get_provider("mock") in production raises ConfigurationError
 7. get_provider("rules_only") in production returns RulesOnlyProvider
 8. get_provider("rules_only") in development returns RulesOnlyProvider
 9. get_provider("unknown_name") raises ConfigurationError
10. get_provider(None) with get_settings raising ValidationError raises ConfigurationError
"""
from unittest.mock import patch
from pydantic import ValidationError
import pytest

from app.config import Settings
from app.errors import ConfigurationError
from app.agents.llm_provider import (
    GroqProvider,
    MockProvider,
    OpenAIProvider,
    RulesOnlyProvider,
    get_provider,
)


def test_1_groq_missing_api_key_raises_configuration_error():
    """get_provider('groq', api_key='') must raise ConfigurationError instead of falling back to MockProvider."""
    dev_settings = Settings(environment="development", groq_api_key="")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        with pytest.raises(ConfigurationError, match="Groq API key"):
            get_provider("groq", api_key="")


# NOTE (SEC-01c): test_2_groq_valid_api_key_returns_groq_provider only asserts isinstance +
# provider_name prefix. A dead GroqProvider (groq package missing, client=None) still passes. Tracked for WS5.
def test_2_groq_valid_api_key_returns_groq_provider():
    """get_provider('groq', api_key='sk-test') returns GroqProvider."""
    dev_settings = Settings(environment="development", groq_api_key="sk-test")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        provider = get_provider("groq", api_key="sk-test")
        assert isinstance(provider, GroqProvider)
        assert provider.provider_name.startswith("groq/")


def test_3_openai_missing_api_key_raises_configuration_error():
    """get_provider('openai', api_key='') must raise ConfigurationError."""
    dev_settings = Settings(environment="development", openai_api_key="")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        with pytest.raises(ConfigurationError, match="OpenAI API key"):
            get_provider("openai", api_key="")


def test_4_openai_valid_api_key_returns_openai_provider():
    """get_provider('openai', api_key='sk-test') returns OpenAIProvider."""
    dev_settings = Settings(environment="development", openai_api_key="sk-test")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        provider = get_provider("openai", api_key="sk-test")
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name.startswith("openai/")


def test_5_mock_in_development_returns_mock_provider():
    """get_provider('mock') in development environment returns MockProvider."""
    dev_settings = Settings(environment="development")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        provider = get_provider("mock")
        assert isinstance(provider, MockProvider)
        assert provider.provider_name == "mock"


def test_6_mock_in_production_raises_configuration_error():
    """get_provider('mock') in production environment raises ConfigurationError."""
    prod_settings = Settings(environment="production")
    with patch("app.agents.llm_provider.get_settings", return_value=prod_settings):
        with pytest.raises(ConfigurationError, match="MockProvider is forbidden in production"):
            get_provider("mock")


def test_7_rules_only_in_production_returns_rules_only_provider():
    """get_provider('rules_only') in production returns RulesOnlyProvider."""
    prod_settings = Settings(environment="production")
    with patch("app.agents.llm_provider.get_settings", return_value=prod_settings):
        provider = get_provider("rules_only")
        assert isinstance(provider, RulesOnlyProvider)
        assert provider.provider_name == "rules_only"


def test_8_rules_only_in_development_returns_rules_only_provider():
    """get_provider('rules_only') in development returns RulesOnlyProvider."""
    dev_settings = Settings(environment="development")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        provider = get_provider("rules_only")
        assert isinstance(provider, RulesOnlyProvider)
        assert provider.provider_name == "rules_only"


def test_9_unknown_provider_raises_configuration_error():
    """get_provider('unknown_provider') raises ConfigurationError instead of falling back to MockProvider."""
    dev_settings = Settings(environment="development")
    with patch("app.agents.llm_provider.get_settings", return_value=dev_settings):
        with pytest.raises(ConfigurationError, match="Unknown LLM provider"):
            get_provider("unknown_provider")


def test_10_none_provider_with_settings_error_raises_configuration_error():
    """get_provider(None) raises ConfigurationError when settings parsing fails."""
    val_error = ValidationError.from_exception_data(title="SettingsError", line_errors=[])
    with patch("app.agents.llm_provider.get_settings", side_effect=val_error):
        with pytest.raises(ConfigurationError):
            get_provider(None)
