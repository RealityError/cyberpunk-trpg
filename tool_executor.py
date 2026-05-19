from typing import Any, Callable

from pydantic import ValidationError

from models import SessionCheckActionRequest, ToolExecutionResult


def execute_agent_tool_calls(
    *,
    session_id: str,
    calls: list[dict[str, Any]],
    run_check_action: Callable[[str, SessionCheckActionRequest], Any],
    tool_handlers: dict[tuple[str, str], Callable[[dict[str, Any]], Any]] | None = None,
) -> list[ToolExecutionResult]:
    results: list[ToolExecutionResult] = []
    allowed_check_path = f"/api/sessions/{session_id}/actions/check"
    tool_handlers = tool_handlers or {}

    for call in calls:
        method = str(call.get("method", "")).upper()
        path = str(call.get("path", ""))
        if method == "POST" and path == allowed_check_path:
            try:
                payload = SessionCheckActionRequest(**call.get("body", {}))
                result = run_check_action(session_id, payload)
            except ValidationError as exc:
                results.append(
                    ToolExecutionResult(
                        call=call,
                        executed=False,
                        error=f"工具参数不符合接口要求：{exc.errors()}",
                    )
                )
                continue
            except Exception as exc:
                results.append(
                    ToolExecutionResult(
                        call=call,
                        executed=False,
                        error=str(exc),
                    )
                )
                continue

            results.append(
                ToolExecutionResult(
                    call=call,
                    executed=True,
                    result=result.model_dump(),
                )
            )
            continue

        handler = tool_handlers.get((method, path))
        if handler is None:
            results.append(
                ToolExecutionResult(
                    call=call,
                    executed=False,
                    error="工具调用不在白名单中。",
                )
            )
            continue

        try:
            result = handler(call.get("body", {}))
        except ValidationError as exc:
            results.append(
                ToolExecutionResult(
                    call=call,
                    executed=False,
                    error=f"工具参数不符合接口要求：{exc.errors()}",
                )
            )
            continue
        except Exception as exc:
            results.append(ToolExecutionResult(call=call, executed=False, error=str(exc)))
            continue

        results.append(
            ToolExecutionResult(
                call=call,
                executed=True,
                result=result.model_dump(),
            )
        )

    return results
