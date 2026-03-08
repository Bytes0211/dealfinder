"""Deal endpoints for the Deal Finder REST API.

Endpoints:
    GET /deals        — paginated list with optional status filter
    GET /deals/top    — high-value deals sorted by discount percentage
    GET /deals/{id}   — single deal detail
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from dealfinder.api.schemas import DealListResponse, DealResponse
from dealfinder.api.deps import get_db
from dealfinder.db.models import Deal, DealStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deals", tags=["deals"])


@router.get("", response_model=DealListResponse, summary="List deals")
async def list_deals(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DealListResponse:
    """Return a paginated list of deals.

    Args:
        status_filter: Optional status filter (e.g. ``evaluated``, ``notified``).
        limit: Maximum number of results to return (default 50, max 200).
        offset: Number of results to skip for pagination.
        db: Injected database session.

    Returns:
        Paginated list of deal summaries with total count.
    """
    query = select(Deal).options(selectinload(Deal.source))
    count_query = select(func.count()).select_from(Deal)

    if status_filter:
        try:
            deal_status = DealStatus(status_filter)
            query = query.where(Deal.status == deal_status)
            count_query = count_query.where(Deal.status == deal_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid status value: {status_filter!r}",
            )

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = query.order_by(desc(Deal.discovered_at)).offset(offset).limit(limit)
    result = await db.execute(query)
    deals = result.scalars().all()

    items = []
    for deal in deals:
        raw = deal.raw_data or {}
        items.append(DealResponse(
            id=deal.id,
            title=deal.title,
            url=deal.url,
            sale_price=deal.sale_price,
            original_price=deal.original_price,
            estimated_value=deal.estimated_value,
            discount_percentage=deal.discount_percentage,
            is_high_value=deal.is_high_value,
            brand=deal.brand,
            status=deal.status.value,
            source_name=deal.source.name if deal.source else None,
            in_stock=raw.get("in_stock"),
            trend=raw.get("trend"),
            trend_confidence=raw.get("trend_confidence"),
            price_trend=raw.get("price_trend"),
            discount_frequency=raw.get("discount_frequency"),
            stockouts_last_30_days=raw.get("stockouts_last_30_days"),
            review_velocity=raw.get("review_velocity"),
            competitor_activity=raw.get("competitor_activity"),
            trend_summary=raw.get("trend_summary"),
        ))

    return DealListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/top", response_model=list[DealResponse], summary="Top high-value deals")
async def top_deals(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> list[DealResponse]:
    """Return high-value deals sorted by discount percentage descending.

    Args:
        limit: Maximum number of deals to return (default 20, max 100).
        db: Injected database session.

    Returns:
        List of high-value deals sorted by discount percentage.
    """
    result = await db.execute(
        select(Deal)
        .where(Deal.is_high_value == True)  # noqa: E712
        .order_by(desc(Deal.discount_percentage))
        .limit(limit)
        .options(selectinload(Deal.source))
    )
    deals = result.scalars().all()

    return [
        DealResponse(
            id=deal.id,
            title=deal.title,
            url=deal.url,
            sale_price=deal.sale_price,
            original_price=deal.original_price,
            estimated_value=deal.estimated_value,
            discount_percentage=deal.discount_percentage,
            is_high_value=deal.is_high_value,
            brand=deal.brand,
            status=deal.status.value,
            source_name=deal.source.name if deal.source else None,
            in_stock=(deal.raw_data or {}).get("in_stock"),
            trend=(deal.raw_data or {}).get("trend"),
            trend_confidence=(deal.raw_data or {}).get("trend_confidence"),
            price_trend=(deal.raw_data or {}).get("price_trend"),
            discount_frequency=(deal.raw_data or {}).get("discount_frequency"),
            stockouts_last_30_days=(deal.raw_data or {}).get("stockouts_last_30_days"),
            review_velocity=(deal.raw_data or {}).get("review_velocity"),
            competitor_activity=(deal.raw_data or {}).get("competitor_activity"),
            trend_summary=(deal.raw_data or {}).get("trend_summary"),
        )
        for deal in deals
    ]


@router.get("/{deal_id}", response_model=DealResponse, summary="Get deal by ID")
async def get_deal(deal_id: UUID, db: AsyncSession = Depends(get_db)) -> DealResponse:
    """Return a single deal by its UUID.

    Args:
        deal_id: UUID of the deal to retrieve.
        db: Injected database session.

    Returns:
        Deal detail response.

    Raises:
        HTTPException 404: If the deal does not exist.
    """
    result = await db.execute(
        select(Deal)
        .where(Deal.id == deal_id)
        .options(selectinload(Deal.source))
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    raw = deal.raw_data or {}
    return DealResponse(
        id=deal.id,
        title=deal.title,
        url=deal.url,
        sale_price=deal.sale_price,
        original_price=deal.original_price,
        estimated_value=deal.estimated_value,
        discount_percentage=deal.discount_percentage,
        is_high_value=deal.is_high_value,
        brand=deal.brand,
        status=deal.status.value,
        source_name=deal.source.name if deal.source else None,
        in_stock=raw.get("in_stock"),
        trend=raw.get("trend"),
        trend_confidence=raw.get("trend_confidence"),
        price_trend=raw.get("price_trend"),
        discount_frequency=raw.get("discount_frequency"),
        stockouts_last_30_days=raw.get("stockouts_last_30_days"),
        review_velocity=raw.get("review_velocity"),
        competitor_activity=raw.get("competitor_activity"),
        trend_summary=raw.get("trend_summary"),
    )
