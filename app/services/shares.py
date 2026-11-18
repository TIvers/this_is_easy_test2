"""Pure helpers for splitting offer traffic shares."""
from __future__ import annotations

from typing import Iterable, Protocol

TOTAL = 100


class ShareError(ValueError):
    pass


class ShareItem(Protocol):
    offer_id: int
    share: int
    pinned: bool


def rebalance(items: Iterable[ShareItem]) -> None:
    items = list(items)
    pinned_sum = sum(item.share for item in items if item.pinned)
    if pinned_sum > TOTAL:
        raise ShareError(f"Сумма закреплённых долей {pinned_sum}% больше {TOTAL}%")
    free = [item for item in items if not item.pinned]
    if not free:
        return
    available = TOTAL - pinned_sum
    if available < len(free):
        raise ShareError(
            f"После закреплённых долей остаётся {available}%, "
            f"но незакреплённым офферам нужно минимум {len(free)}%"
        )
    base, extra = divmod(available, len(free))
    for index, item in enumerate(free):
        item.share = base + (1 if index < extra else 0)


def initial_pins(shares: list[int]) -> list[bool]:
    if not shares:
        return []
    even = TOTAL / len(shares)
    return [not all(abs(value - even) <= 1 for value in shares)] * len(shares)


def total(items: Iterable[ShareItem]) -> int:
    return sum(item.share for item in items)


def add_item(items: list[ShareItem], item: ShareItem) -> None:
    if any(existing.offer_id == item.offer_id for existing in items):
        raise ShareError("Этот оффер уже есть в потоке")
    previous_share, previous_pinned = item.share, item.pinned
    item.pinned = False
    items.append(item)
    try:
        rebalance(items)
    except Exception:
        items.pop()
        item.share, item.pinned = previous_share, previous_pinned
        raise


def remove_item(items: list[ShareItem], offer_id: int) -> ShareItem:
    for index, item in enumerate(items):
        if item.offer_id == offer_id:
            del items[index]
            try:
                rebalance(items)
            except Exception:
                items.insert(index, item)
                raise
            return item
    raise ShareError("Оффера нет в потоке")


def set_share(items: list[ShareItem], offer_id: int, share: int) -> None:
    if not 0 <= share <= TOTAL:
        raise ShareError("Доля должна быть от 0 до 100")
    target = next((item for item in items if item.offer_id == offer_id), None)
    if target is None:
        raise ShareError("Оффера нет в потоке")
    others_pinned = sum(item.share for item in items if item.pinned and item is not target)
    if others_pinned + share > TOTAL:
        raise ShareError("Сумма закреплённых долей не может превышать 100%")
    free_count = sum(not item.pinned for item in items if item is not target)
    if free_count and TOTAL - others_pinned - share < free_count:
        raise ShareError(
            f"Оставшейся доли не хватит минимум по 1% для {free_count} незакреплённых офферов"
        )
    target.share = share
    target.pinned = True
    rebalance(items)


def unpin(items: list[ShareItem], offer_id: int) -> None:
    target = next((item for item in items if item.offer_id == offer_id), None)
    if target is None:
        raise ShareError("Оффера нет в потоке")
    pinned_sum = sum(item.share for item in items if item.pinned and item is not target)
    free_count = sum(not item.pinned for item in items) + (1 if target.pinned else 0)
    if TOTAL - pinned_sum < free_count:
        raise ShareError(
            f"Оставшейся доли не хватит минимум по 1% для {free_count} незакреплённых офферов"
        )
    target.pinned = False
    rebalance(items)


def validate_for_push(items: Iterable[ShareItem]) -> None:
    items = list(items)
    if not items:
        raise ShareError("Нельзя сохранить поток без офферов")
    if total(items) != TOTAL:
        raise ShareError("Сумма долей офферов должна быть равна 100%")
