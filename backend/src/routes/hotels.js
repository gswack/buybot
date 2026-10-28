const express = require("express");
const router = express.Router();
const hotels = require("../data/hotels.json");

router.get("/", (req, res) => {
  res.json(hotels);
});

module.exports = router;
