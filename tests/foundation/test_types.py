import unittest
from dataclasses import fields
from datetime import datetime

from foundation import types

DOMAIN_CLASSES = [
    types.Task,
    types.SubTask,
    types.Workflow,
    types.Design,
    types.Implementation,
    types.TestResult,
    types.PullRequest,
    types.Review,
    types.Knowledge,
    types.Context,
    types.Configuration,
    types.Notification,
    types.CommunicationMessage,
    types.Repository,
]


class DomainModelCommonAttributesTest(unittest.TestCase):
    def test_all_domain_models_share_common_field_names_and_types(self) -> None:
        expected = {"id": str, "created_at": datetime, "updated_at": datetime, "metadata": dict}
        for cls in DOMAIN_CLASSES:
            field_types = {f.name: f.type for f in fields(cls)}
            self.assertEqual(set(field_types), set(expected), msg=cls.__name__)

    def test_each_domain_default_fields_are_generated(self) -> None:
        for cls in DOMAIN_CLASSES:
            instance = cls()
            self.assertIsInstance(instance.id, str, msg=cls.__name__)
            self.assertIsInstance(instance.created_at, datetime, msg=cls.__name__)
            self.assertIsInstance(instance.updated_at, datetime, msg=cls.__name__)
            self.assertEqual(instance.metadata, {}, msg=cls.__name__)

    def test_task_id_is_unique_across_instances(self) -> None:
        self.assertNotEqual(types.Task().id, types.Task().id)

    def test_task_metadata_defaults_to_empty_dict(self) -> None:
        self.assertEqual(types.Task().metadata, {})


if __name__ == "__main__":
    unittest.main()
