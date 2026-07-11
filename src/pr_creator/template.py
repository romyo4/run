"""PRテンプレート(Summary/Purpose/Changes/Test Result/Related Issue/Notes)生成ロジック(IS11 2章 template.py)。

`PullRequestTemplate`からMarkdown本文を組み立てる純関数群。Title生成ロジックも含む。
"""

from __future__ import annotations

from pr_creator.models import (
    ImplementationResultLike,
    PullRequestTemplate,
    TestReportLike,
)

__all__ = ["render", "build_title", "build_template"]

_NOT_SPECIFIED = "N/A"
_NO_CHANGES = "(変更ファイルなし)"


def _implementation_metadata(implementation_result: ImplementationResultLike) -> dict[str, object]:
    """`implementation_result`から`Implementation`(Foundation Domain)のmetadataを取り出す。

    実際の`implementation_result`は Executor(M09)の`executor.models.ImplementationResult`
    (`.implementation`属性にFoundation `Implementation`を保持する)であることを想定するが、
    Foundation `Implementation`自体が直接渡された場合(テスト等)にも対応できるよう、
    `.implementation`が無ければ`implementation_result`自体をFoundation Domainとして扱う
    (ダックタイピング、2026-07 統合レビューの是正)。
    """
    inner = getattr(implementation_result, "implementation", None)
    target = inner if inner is not None else implementation_result
    return getattr(target, "metadata", None) or {}


def _changed_file_paths(implementation_result: ImplementationResultLike) -> list[str]:
    """変更ファイル一覧を取得する(IS11 2.1「変更ファイル一覧取得」)。

    変更ファイルの実体はExecutor(M09)の`ImplementationResult.modified_files`
    (`ModifiedFile.path`の一覧)であり、`Implementation.metadata`には
    件数(`modified_file_count`)しか含まれない(2026-07 統合レビューで判明した不整合の
    是正: 従来は存在しない`metadata["changed_files"]`を参照しており常に空になっていた)。
    `modified_files`が取得できない場合は、後方互換のため`metadata["changed_files"]`
    (明示的に付与されている場合)へフォールバックする。
    """
    modified_files = getattr(implementation_result, "modified_files", None)
    if modified_files:
        return [str(getattr(modified_file, "path", modified_file)) for modified_file in modified_files]
    metadata = _implementation_metadata(implementation_result)
    return list(metadata.get("changed_files", []) or [])


def render(template: PullRequestTemplate) -> str:
    """PullRequestTemplateから、固定順(Summary/Purpose/Changes/Test Result/Related Issue/Notes)の
    Markdown本文を生成する。"""
    changes_section = "\n".join(f"- {item}" for item in template.changes) if template.changes else _NO_CHANGES
    related_issue = template.related_issue if template.related_issue else _NOT_SPECIFIED
    notes = template.notes if template.notes else _NOT_SPECIFIED
    return (
        "# Summary\n\n"
        f"{template.summary}\n\n"
        "## Purpose\n\n"
        f"{template.purpose}\n\n"
        "## Changes\n\n"
        f"{changes_section}\n\n"
        "## Test Result\n\n"
        f"{template.test_result}\n\n"
        "## Related Issue\n\n"
        f"{related_issue}\n\n"
        "## Notes\n\n"
        f"{notes}\n"
    )


def build_title(implementation_result: ImplementationResultLike, workflow_id: str) -> str:
    """implementation_result(のImplementation部分)のmetadataの'title'または'summary'と
    workflow_idからTitleを生成する。"""
    metadata = _implementation_metadata(implementation_result)
    subject = metadata.get("title") or metadata.get("summary") or "Implementation"
    return f"[{workflow_id}] {subject}"


def build_template(
    implementation_result: ImplementationResultLike,
    test_report: TestReportLike,
    project_context: dict[str, object],
) -> PullRequestTemplate:
    """implementation_result / test_report / project_contextからPullRequestTemplateを組み立てる。

    Test Result欄はTester(M10)が実際に生成する`TestReport.summary`
    (例: "Quality Gate PASS: 6/6 item(s) passed.")を用いる(2026-07 統合レビューの是正:
    従来は存在しない`test_report.metadata["test_result_summary"]`を参照しており常に
    既定値"PASSED"に固定化されていた)。
    """
    impl_metadata = _implementation_metadata(implementation_result)
    changes = _changed_file_paths(implementation_result)
    test_result_summary = getattr(test_report, "summary", None) or "PASSED"
    return PullRequestTemplate(
        summary=str(impl_metadata.get("summary", "")),
        purpose=str(impl_metadata.get("purpose", "")),
        changes=changes,
        test_result=str(test_result_summary),
        related_issue=project_context.get("related_issue"),
        notes=project_context.get("notes"),
    )
