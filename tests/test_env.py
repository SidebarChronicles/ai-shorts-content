"""Smoke tests for scripts/_env.py — guards against silent secret-loading bugs."""
import os

from _env import load_dotenv


def _isolate_env(*keys):
    """Remove keys from os.environ for the duration of a test."""
    for k in keys:
        os.environ.pop(k, None)


def test_load_dotenv_basic(tmp_path):
    _isolate_env("TEST_K1", "TEST_K2")
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_K1=foo\nTEST_K2=bar\n")
    n = load_dotenv(env_file)
    assert n == 2
    assert os.environ["TEST_K1"] == "foo"
    assert os.environ["TEST_K2"] == "bar"
    _isolate_env("TEST_K1", "TEST_K2")


def test_load_dotenv_strips_double_quotes(tmp_path):
    _isolate_env("TEST_QUOTED")
    env_file = tmp_path / ".env"
    env_file.write_text('TEST_QUOTED="sk-xxx-yyy"\n')
    load_dotenv(env_file)
    assert os.environ["TEST_QUOTED"] == "sk-xxx-yyy"
    _isolate_env("TEST_QUOTED")


def test_load_dotenv_strips_single_quotes(tmp_path):
    _isolate_env("TEST_SINGLE")
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_SINGLE='hello'\n")
    load_dotenv(env_file)
    assert os.environ["TEST_SINGLE"] == "hello"
    _isolate_env("TEST_SINGLE")


def test_load_dotenv_inline_comment(tmp_path):
    _isolate_env("TEST_COMMENT")
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_COMMENT=foo # trailing comment\n")
    load_dotenv(env_file)
    assert os.environ["TEST_COMMENT"] == "foo"
    _isolate_env("TEST_COMMENT")


def test_load_dotenv_skips_comments_and_blank(tmp_path):
    _isolate_env("REAL_K")
    env_file = tmp_path / ".env"
    env_file.write_text("# top comment\n\nREAL_K=v\n  # indented\n")
    n = load_dotenv(env_file)
    assert n == 1
    assert os.environ["REAL_K"] == "v"
    _isolate_env("REAL_K")


def test_load_dotenv_setdefault_semantics(tmp_path):
    """Pre-set env vars (e.g. from cron) must win over .env."""
    os.environ["TEST_PRESET"] = "from_cron"
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_PRESET=from_dotenv\n")
    load_dotenv(env_file)
    assert os.environ["TEST_PRESET"] == "from_cron"
    _isolate_env("TEST_PRESET")


def test_load_dotenv_missing_file(tmp_path):
    n = load_dotenv(tmp_path / "nonexistent.env")
    assert n == 0


def test_load_dotenv_value_with_equals(tmp_path):
    _isolate_env("TEST_EQUALS")
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_EQUALS=a=b=c\n")
    load_dotenv(env_file)
    assert os.environ["TEST_EQUALS"] == "a=b=c"
    _isolate_env("TEST_EQUALS")
