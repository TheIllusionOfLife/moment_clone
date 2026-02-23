import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before they are imported by the modules under test
mock_sqlmodel = MagicMock()
sys.modules["sqlmodel"] = mock_sqlmodel
sys.modules["sqlmodel.text"] = MagicMock()
sys.modules["sqlmodel.pool"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()

# Mock other helpers
sys.modules["backend.core.database"] = MagicMock()
sys.modules["backend.core.settings"] = MagicMock()
sys.modules["pipeline.stages.db_helpers"] = MagicMock()

# Mock the models used in run_rag
class MockModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
    def __getattr__(self, name):
        return None

sys.modules["backend.models.dish"] = MagicMock()
sys.modules["backend.models.dish"].Dish = MockModel
sys.modules["backend.models.session"] = MagicMock()
sys.modules["backend.models.session"].CookingSession = MockModel
sys.modules["backend.models.learner_state"] = MagicMock()
sys.modules["backend.models.learner_state"].LearnerState = MockModel

# Set up path to allow importing from the root
sys.path.append(".")

# Import the stage logic after mocking its dependencies
from pipeline.stages.rag import run_rag

def _make_session(diagnosis: str | None = None) -> MockModel:
    return MockModel(
        user_id=10,
        dish_id=5,
        session_number=1,
        status="processing",
        video_analysis={"diagnosis": diagnosis} if diagnosis else None,
    )

def _make_dish(principles: list | None = None) -> MockModel:
    d = MockModel(
        slug="chahan",
        name_ja="チャーハン",
        name_en="Fried Rice",
        description_ja="炒飯",
        order=1,
        principles=principles,
    )
    d.name_ja = "チャーハン"
    return d

class TestRagQueryConstruction(unittest.TestCase):
    def setUp(self):
        # Reset mocks before each test case
        self.mock_client_instance = MagicMock()
        self.mock_embed_response = MagicMock()
        self.mock_client_instance.models.embed_content.return_value = self.mock_embed_response
        self.mock_embed_response.embeddings = [MagicMock(values=[0.1] * 768)]

    def test_run_rag_query_construction(self):
        cases = [
            ("火加減", ["原則1", "原則2"], "火加減 原則1 原則2"),
            ("火加減", [], "火加減"),
            (None, ["原則1", "原則2"], "原則1 原則2"),
            (None, None, "チャーハン"),
            (None, [], "チャーハン"),
        ]

        for diagnosis, principles, expected_query in cases:
            with self.subTest(diagnosis=diagnosis, principles=principles):
                fake_session = _make_session(diagnosis)
                fake_dish = _make_dish(principles)
                fake_ls = MockModel(user_id=10, session_summaries=[])

                with patch("pipeline.stages.rag.genai.Client", return_value=self.mock_client_instance), \
                     patch("pipeline.stages.rag.get_session_with_dish", return_value=(fake_session, fake_dish)), \
                     patch("pipeline.stages.rag.get_or_create_learner_state", return_value=fake_ls), \
                     patch("pipeline.stages.rag.get_engine"), \
                     patch("pipeline.stages.rag.DBSession") as mock_db_session_cls, \
                     patch("pipeline.stages.rag.settings") as mock_settings:

                    mock_settings.GEMINI_EMBEDDING_MODEL = "fake-model"

                    # Mock DBSession instance
                    mock_db_session = MagicMock()
                    mock_db_session.__enter__.return_value = mock_db_session
                    mock_db_session_cls.return_value = mock_db_session
                    mock_db_session.execute.return_value.fetchall.return_value = [("原則1",)]

                    # Reset call count for each subtest
                    self.mock_client_instance.models.embed_content.reset_mock()

                    run_rag(1)

                    # Verify embed_content call
                    self.mock_client_instance.models.embed_content.assert_called_once_with(
                        model="fake-model",
                        contents=expected_query,
                    )

if __name__ == "__main__":
    unittest.main()
