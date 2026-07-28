export default function EmptyState({ icon, title, body, children }) {
  return (
    <div className="state">
      {icon && (
        <span className="state__icon" aria-hidden="true">
          {icon}
        </span>
      )}
      <h2 className="state__title">{title}</h2>
      {body && <p className="state__body">{body}</p>}
      {children && <div className="state__actions">{children}</div>}
    </div>
  );
}
