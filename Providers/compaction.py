from agent_framework._compaction import CompactionStrategy


class DebugStrategy(CompactionStrategy):
    def __init__(self, name: str, inner: CompactionStrategy):
        self._name = name
        self._inner = inner
        print(f"🔧 DebugStrategy '{name}' initialized")

    async def __call__(self, messages):
        groups_before = self._count_groups(messages)
        tokens_before = self._token_count(messages)
        excluded_before = self._count_excluded(messages)

        print(f"\n[DEBUG] {self._name} CALLED")
        print(f"[DEBUG] Messages BEFORE: {len(messages)}")
        print(f"[DEBUG] Groups BEFORE: {groups_before}")
        print(f"[DEBUG] Tokens BEFORE: {tokens_before}")
        print(f"[DEBUG] Excluded BEFORE: {excluded_before}")

        result = await self._inner(messages)

        groups_after = self._count_groups(messages)
        tokens_after = self._token_count(messages)
        excluded_after = self._count_excluded(messages)

        print(f"[DEBUG] Messages AFTER: {len(messages)}")
        print(f"[DEBUG] Groups AFTER: {groups_after}")
        print(f"[DEBUG] Tokens AFTER: {tokens_after}")
        print(f"[DEBUG] Excluded AFTER: {excluded_after}")
        print(f"[DEBUG] Changed: {result}")
        print(f"[DEBUG] {self._name} DONE\n")

        return result

    @staticmethod
    def _count_groups(messages):
        group_ids = set()
        for message in messages:
            additional_properties = getattr(message, "additional_properties", {}) or {}
            group_annotation = additional_properties.get("_group") or {}
            group_id = group_annotation.get("id")
            if isinstance(group_id, str) and group_id:
                group_ids.add(group_id)
        return len(group_ids)

    @staticmethod
    def _token_count(messages):
        total = 0
        for message in messages:
            additional_properties = getattr(message, "additional_properties", {}) or {}
            group_annotation = additional_properties.get("_group") or {}
            token_count = group_annotation.get("token_count")
            if isinstance(token_count, int):
                total += token_count
        return total

    @staticmethod
    def _count_excluded(messages):
        total = 0
        for message in messages:
            additional_properties = getattr(message, "additional_properties", {}) or {}
            if additional_properties.get("_excluded") is True:
                total += 1
        return total