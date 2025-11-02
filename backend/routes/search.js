const express = require("express");
const axios = require("axios");
const router = express.Router();

const PRICEAPI_TOKEN = "WYFFNWJQQDDDGMENLLXQNYWLQOTJEPQJAHVQDARBPQTUXBBADNTLKQLPOXTOSXCC"; // Replace with your actual token

router.get("/search", async (req, res) => {
  const query = req.query.query;  
  const cardType = req.query.cardType || "none"; // e.g., 'visa', 'mastercard'  
  
  if (!query) return res.status(400).json({ error: "Missing query parameter" });

  const discountRates = {
    visa: 0.05,
    mastercard: 0.10,
    amex: 0.07,
  };

  const discount = discountRates[cardType.toLowerCase()] || 0;

  // const discountedResults = resultResponse.data.products.map((product) => {
  //   return {
  //     ...product,
  //     discountedPrice: (product.price * (1 - discount)).toFixed(2),
  //     discountApplied: `${discount * 100}%`,
  //   };
  // });

  // res.json(discountedResults);

  
  // if (!query) return res.status(400).json({ error: "Missing query parameter" });

  try {
    // Step 1: Create a job
    const jobResponse = await axios.post("https://api.priceapi.com/jobs", null, {
      params: {
        token: PRICEAPI_TOKEN,
        source: "google-shopping",
        country: "us",
        key: "keyword",
        values: query,
      },
    });

    const jobId = jobResponse.data.job_id;

    // Step 2: Wait and fetch results (simplified with delay)
    await new Promise((resolve) => setTimeout(resolve, 3000)); // wait 3 seconds

    const resultResponse = await axios.get(`https://api.priceapi.com/products/bulk/${jobId}`, {
      params: { token: PRICEAPI_TOKEN },
    });
    
    const products = resultResponse.data.products || [];

    const discountedResults = products.map((product) => ({
      ...product,
      discountedPrice: (product.price * (1 - discount)).toFixed(2),
      discountApplied: `${(discount * 100).toFixed(0)}%`,
    }));

    res.json(discountedResults);
    // res.json(resultResponse.data);
  } catch (error) {
    console.error("PriceAPI error:", error.response?.data || error.message);
    res.status(500).json({ error: "Failed to fetch product data" });
  }
});

module.exports = router;