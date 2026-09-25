"""
Pydantic v2 request / response schemas.

All schemas are re-exported here for convenient imports::

    from app.schemas import UserCreate, TokenResponse, TopicRead, ...
"""

# ── Common ───────────────────────────────────────────────────────────────
from app.schemas.common import (  # noqa: F401
    DetailResponse,
    MessageResponse,
    PaywallResponse,
    RateLimitResponse,
)

# ── Auth & Users ─────────────────────────────────────────────────────────
from app.schemas.auth import (  # noqa: F401
    SubscriptionRead,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserRead,
)

# ── Curriculum ───────────────────────────────────────────────────────────
from app.schemas.curriculum import (  # noqa: F401
    ModuleRead,
    ModuleWithTopicsRead,
    TopicAttachmentRead,
    TopicContentRead,
    TopicDetailRead,
    TopicRead,
)

# ── Progress ─────────────────────────────────────────────────────────────
from app.schemas.progress import (  # noqa: F401
    ModuleProgressSummary,
    ProgressRead,
    ProgressUpdate,
)

# ── AI ───────────────────────────────────────────────────────────────────
from app.schemas.ai import (  # noqa: F401
    AIQueryRequest,
    AIQueryResponse,
    AIQuotaResponse,
)

# ── Admin CMS ────────────────────────────────────────────────────────────
from app.schemas.admin_cms import (  # noqa: F401
    AdminAttachmentRead,
    AdminModuleRead,
    AdminTopicContentRead,
    AdminTopicRead,
    ModuleCreate,
    ModuleUpdate,
    TopicCreate,
    TopicUpdate,
)

# ── Admin Analytics ──────────────────────────────────────────────────────
from app.schemas.admin_analytics import (  # noqa: F401
    AIUtilizationAnalytics,
    CompletionFunnelItem,
    FinanceSummaryAnalytics,
    LearningEngagementAnalytics,
    OverviewAnalytics,
    PaymentMethodBreakdown,
    RecentTransaction,
    TopAIUser,
    TopicEngagement,
)

