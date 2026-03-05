import { useParams, Link } from 'react-router-dom';
import { useDeal } from '../hooks';

function row(label: string, value: string | null | undefined) {
  if (!value) return null;
  return (
    <tr>
      <th>{label}</th>
      <td>{value}</td>
    </tr>
  );
}

function fmtPrice(val: string | null): string {
  return val ? `$${parseFloat(val).toFixed(2)}` : '—';
}

export function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: deal, isLoading, isError } = useDeal(id ?? '');

  if (isLoading) return <div className="page"><p className="state-msg">Loading…</p></div>;
  if (isError || !deal) {
    return (
      <div className="page">
        <p className="state-msg state-msg--error">Deal not found.</p>
        <Link to="/" className="btn btn-outline">← Back to Feed</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <Link to="/" className="back-link">← Feed</Link>
      <div className="deal-detail">
        <div className="deal-detail-header">
          <h1>{deal.title}</h1>
          {deal.is_high_value && <span className="badge badge--hot">🔥 Hot Deal</span>}
        </div>

        <table className="detail-table">
          <tbody>
            {row('Sale Price', fmtPrice(deal.sale_price))}
            {row('Original Price', fmtPrice(deal.original_price))}
            {row('Estimated Value', fmtPrice(deal.estimated_value))}
            {row('Discount', deal.discount_percentage
              ? `${parseFloat(deal.discount_percentage).toFixed(1)}%`
              : null)}
            {row('Category', deal.category)}
            {row('Brand', deal.brand)}
            {row('Source', deal.source_name)}
            {row('Status', deal.status)}
          </tbody>
        </table>

        <a href={deal.url} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
          View Deal ↗
        </a>
      </div>
    </div>
  );
}
