interface Props {
  text: string;
}

/** Inline ⓘ icon that shows a tooltip on hover/focus. */
export function InfoTooltip({ text }: Props) {
  return (
    <span className="info-tooltip" aria-label={text}>
      <span className="info-tooltip-icon" tabIndex={0} aria-describedby={undefined}>ⓘ</span>
      <span className="info-tooltip-bubble" role="tooltip">{text}</span>
    </span>
  );
}
