import { Link } from 'react-router-dom';
import type { DealResponse } from '../api/types';

interface Props {
  deal: DealResponse;
}

function fmt(val: string | null, prefix = '$'): string {
  return val ? `${prefix}${parseFloat(val).toFixed(2)}` : '—';
}

/** Extract short domain label from a URL, e.g. "amazon" from "https://www.amazon.ca/..." */
function shortDomain(url: string): string | null {
  try {
    const host = new URL(url).hostname.replace(/^www\./, '');
    return host.split('.')[0] || null;
  } catch {
    return null;
  }
}

export function DealCard({ deal }: Props) {
  return (
    <div className={`deal-card${deal.is_high_value ? ' deal-card--hot' : ''}`}>
      <div className="deal-card-header">
        <Link to={`/deals/${deal.id}`} className="deal-title">{deal.title}</Link>
        {deal.is_high_value && <span className="badge badge--hot">🔥 Hot Deal</span>}
      </div>

      <div className="deal-card-meta">
        {deal.brand && <span className="tag">{deal.brand}</span>}
        {deal.source_name && <span className="tag tag--muted">{deal.source_name}</span>}
        {(deal.sale_price || deal.original_price) && (
          <span className="deal-card-meta-prices">
            {deal.sale_price && <span className="price price--sale">{fmt(deal.sale_price)}</span>}
            {deal.original_price && (
              <span className="price price--original">{fmt(deal.original_price)}</span>
            )}
            {deal.discount_percentage && (
              <span className="badge badge--discount">
                {parseFloat(deal.discount_percentage).toFixed(0)}% off
              </span>
            )}
          </span>
        )}
      </div>

      <div className="deal-card-footer">
        {deal.in_stock === false && <span className="badge badge--oos">Out of Stock</span>}
        <span className={`status status--${deal.status}`}>{deal.status}</span>
        {shortDomain(deal.url) && <span className="deal-card-domain">{shortDomain(deal.url)}</span>}
        <a href={deal.url} target="_blank" rel="noopener noreferrer" className="btn btn-sm">
          View Deal ↗
        </a>
      </div>
    </div>
  );
}
