const mongoose = require("mongoose");

const ReservationSchema = new mongoose.Schema({
  reservationId: Number,
  fullName: String,
  email: String,
  checkIn: String,
  checkOut: String,
  hotelId: Number
});

module.exports = mongoose.model("Reservation", ReservationSchema);
