"""Tests for centralized Environment class."""
import os
import pytest
from src.core.environment import Environment


class TestEnvironment:
    def test_current_defaults_to_production(self):
        old = os.environ.pop("ENV", None)
        try:
            assert Environment.current() == "production"
        finally:
            if old:
                os.environ["ENV"] = old

    def test_current_valid_env(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "development"
            assert Environment.current() == "development"
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]

    def test_current_unknown_defaults_to_production(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "unknown_env"
            assert Environment.current() == "production"
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]

    def test_is_production(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "production"
            assert Environment.is_production() is True
            os.environ["ENV"] = "development"
            assert Environment.is_production() is False
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]

    def test_is_development(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "dev"
            assert Environment.is_development() is True
            os.environ["ENV"] = "production"
            assert Environment.is_development() is False
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]

    def test_is_production_or_staging(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "staging"
            assert Environment.is_production_or_staging() is True
            os.environ["ENV"] = "development"
            assert Environment.is_production_or_staging() is False
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]

    def test_valid_environments_set(self):
        expected = {"production", "staging", "development", "dev", "testing", "test", "local"}
        assert Environment.VALID == expected

    def test_current_raw_returns_unknown(self):
        old = os.environ.get("ENV")
        try:
            os.environ["ENV"] = "custom_env"
            assert Environment.current_raw() == "custom_env"
        finally:
            if old:
                os.environ["ENV"] = old
            elif "ENV" in os.environ:
                del os.environ["ENV"]
