function RoleToggle({ role, onChange }) {
  const roles = [
    { value: "card_member", label: "Card Member" },
    { value: "merchant", label: "Merchant" },
  ];

  return (
    <div className="inline-flex rounded-lg border border-gray-300 bg-gray-100 p-0.5">
      {roles.map((r) => (
        <button
          key={r.value}
          type="button"
          onClick={() => onChange(r.value)}
          className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
            role === r.value
              ? "bg-white shadow text-indigo-700"
              : "text-gray-600 hover:text-gray-900"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}

export default RoleToggle;
