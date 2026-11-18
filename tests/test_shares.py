from dataclasses import dataclass

import pytest

from app.services import shares
from app.services.shares import ShareError


@dataclass
class Item:
    offer_id: int
    share: int = 0
    pinned: bool = False


def make(*ids):
    items = []
    for i in ids:
        shares.add_item(items, Item(i))
    return items


def values(items):
    return [i.share for i in items]


def test_single_offer_gets_100():
    assert values(make(1)) == [100]


def test_even_split_four_offers():
    assert values(make(1, 2, 3, 4)) == [25, 25, 25, 25]


def test_three_offers_sum_to_100():
    items = make(1, 2, 3)
    assert values(items) == [34, 33, 33]
    assert shares.total(items) == 100


def test_remove_rebalances():
    items = make(1, 2, 3, 4)
    shares.remove_item(items, 4)
    assert values(items) == [34, 33, 33]
    shares.remove_item(items, 1)
    assert values(items) == [50, 50]


def test_remove_last_offer_leaves_empty():
    items = make(1)
    shares.remove_item(items, 1)
    assert items == []
    with pytest.raises(ShareError):
        shares.validate_for_push(items)


def test_pinned_share_is_kept_on_add_and_remove():
    items = make(1, 2)
    shares.set_share(items, 1, 70)
    assert values(items) == [70, 30]
    shares.add_item(items, Item(3))
    assert values(items) == [70, 15, 15]
    shares.remove_item(items, 3)
    assert values(items) == [70, 30]


def test_unpin_returns_to_even_split():
    items = make(1, 2)
    shares.set_share(items, 1, 70)
    shares.unpin(items, 1)
    assert values(items) == [50, 50]


def test_pinned_over_100_is_rejected_and_state_unchanged():
    items = make(1, 2, 3)
    shares.set_share(items, 1, 60)
    before = values(items)
    with pytest.raises(ShareError):
        shares.set_share(items, 2, 50)
    assert values(items) == before


def test_unpinned_offers_keep_at_least_one_percent_each():
    items = make(1)
    shares.set_share(items, 1, 99)
    shares.add_item(items, Item(2))
    before = values(items)

    with pytest.raises(ShareError, match="минимум"):
        shares.add_item(items, Item(3))

    assert values(items) == before
    assert [item.offer_id for item in items] == [1, 2]


def test_setting_pinned_share_cannot_leave_zero_for_free_offers():
    items = make(1, 2, 3)

    with pytest.raises(ShareError, match="минимум"):
        shares.set_share(items, 1, 99)

    assert values(items) == [34, 33, 33]


def test_all_pinned_and_not_100_blocks_push():
    items = make(1, 2)
    shares.set_share(items, 1, 30)
    shares.set_share(items, 2, 30)
    assert shares.total(items) == 60
    with pytest.raises(ShareError):
        shares.validate_for_push(items)


def test_duplicate_and_unknown_offer():
    items = make(1)
    with pytest.raises(ShareError):
        shares.add_item(items, Item(1))
    with pytest.raises(ShareError):
        shares.remove_item(items, 99)
    with pytest.raises(ShareError):
        shares.set_share(items, 99, 10)


def test_share_bounds():
    items = make(1, 2)
    with pytest.raises(ShareError):
        shares.set_share(items, 1, 101)
    with pytest.raises(ShareError):
        shares.set_share(items, 1, -1)


def test_initial_pins():
    assert shares.initial_pins([]) == []
    assert shares.initial_pins([50, 50]) == [False, False]
    assert shares.initial_pins([34, 33, 33]) == [False, False, False]
    assert shares.initial_pins([70, 30]) == [True, True]
