import { useEffect, useState } from "react";
import { Routes, Route, Link } from "react-router-dom";
import SearchBar from "./SearchBar"; // adjust path if needed

export default function App() {
  const [darkMode, setDarkMode] = useState(() => {
    return localStorage.getItem("theme") === "dark";
  });

  const toggleDarkMode = () => {
    setDarkMode((prev) => !prev);
  };

  useEffect(() => {
    const html = document.documentElement;
    if (darkMode) {
      html.classList.add("dark");
      localStorage.setItem("theme", "dark");
    } else {
      html.classList.remove("dark");
      localStorage.setItem("theme", "light");
    }
  }, [darkMode]);

  const handleSearch = async (query) => {
    try {
      const cardType = "visa"; // You can get this from user input
      const response = await fetch(
        `http://localhost:5000/api/search?query=${encodeURIComponent(query)}&cardType=${cardType}`
      );

      const data = await response.json();
      console.log("Search results:", data);

      // You can now display these results in your UI
    } catch (error) {
      console.error("Error fetching search results:", error);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 text-gray-900 dark:bg-gray-900 dark:text-gray-100 transition-colors duration-300">
      <header className="text-center py-8">
        <h1 className="text-4xl font-bold">🛒 Buybot</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-2">
          Find the best deals with AI-powered price comparison.
        </p>
      </header>

      {/* Dark mode toggle button */}
      <button
        onClick={toggleDarkMode}
        className="mb-4 px-4 py-2 bg-gray-800 dark:bg-gray-100 text-white dark:text-gray-900 rounded-lg shadow hover:opacity-90 transition"
      >
        {darkMode ? "☀️ Light Mode" : "🌙 Dark Mode"}
      </button>

      {/* ✅ Add the SearchBar here */}
      <SearchBar onSearch={handleSearch} />

      <nav className="flex gap-4 mb-6">
        <Link to="/" className="text-blue-600 dark:text-blue-400 hover:underline">
          Home
        </Link>
        <Link to="/about" className="text-blue-600 dark:text-blue-400 hover:underline">
          About
        </Link>
      </nav>

      <main className="text-gray-700 dark:text-gray-300">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/about" element={<AboutPage />} />
        </Routes>
      </main>
    </div>
  );
}

function HomePage() {
  return <p>Search for a product to compare prices across stores.</p>;
}

function AboutPage() {
  return <p>Buybot scans the web for deals and discounts automatically.</p>;
}