import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <p className="text-6xl font-bold text-gray-200">404</p>
      <p className="mt-2 text-sm text-gray-500">Page not found</p>
      <Link
        href="/"
        className="mt-4 rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
      >
        Back to Dashboard
      </Link>
    </div>
  );
}
