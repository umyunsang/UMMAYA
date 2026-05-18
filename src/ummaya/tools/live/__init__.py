# SPDX-License-Identifier: Apache-2.0
"""Live check adapters.

Importing this package registers live check families with the primitive
dispatcher. Keep imports explicit so unrelated live adapters do not load by
accident.
"""

from __future__ import annotations

import ummaya.tools.live.verify_kb_identity  # noqa: F401
