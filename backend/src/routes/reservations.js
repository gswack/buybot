const express = require("express");
const router = express.Router();
const Reservation = require("../models/Reservation");

// Create Reservation
router.post("/", async (req, res) => {
  try {
    const reservation = new Reservation(req.body);
    await reservation.save();

    res.json({
      message: "Reservation created successfully",
      reservation
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Reservation Lookup
router.get("/lookup", async (req, res) => {
  try {
    const query = (req.query.query || "").trim();
    if (!query) {
      return res.status(400).json({
        error: "Search query is required"
      });
  }

    const reservation = await Reservation.findOne({
      $or: [
        { fullName: { $regex: new RegExp(`^${query}$`, "i") } },
        { email: { $regex: new RegExp(`^${query}$`, "i") } }
      ]
    });

    if (!reservation) {
      return res.json({ found: false });
    }

    res.json({ found: true, reservation });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Cancel reservation
router.delete("/:id", async (req, res) => {
  try {
    const deleted = await Reservation.findByIdAndDelete(req.params.id);

  if (!deleted) {
    return res.status(404).json({ error: "Reservation not found." });
  }

    res.json({ message: "Reservation canceled successfully." });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
}); 

module.exports = router;
