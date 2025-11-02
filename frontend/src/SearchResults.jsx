export default function SearchResults({ results }) {
  if (!results.length) return <p className="text-center mt-4">No products found.</p>;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 mt-6">
      {results.map((product) => (
        <div key={product.id} className="border p-4 rounded-lg shadow bg-white dark:bg-gray-800">
          <img
            src={product.image}
            alt={product.name}
            className="w-full h-48 object-cover rounded mb-2"
          />
          <h2 className="text-lg font-semibold">{product.name}</h2>
          <p className="text-sm text-gray-500">{product.brand}</p>
          <p className="text-blue-600 font-bold">${product.price}</p>
        </div>
      ))}
    </div>
  );
}