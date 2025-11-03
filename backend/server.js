require("dotenv").config();
console.log("Loaded token:", process.env.PRICEAPI_TOKEN);

const express = require("express");
const cors = require("cors");
const searchRoutes = require("./routes/search");

const app = express();
app.use(cors());
app.use(express.json());
app.use("/api", searchRoutes);

const PORT = process.env.PORT || 3000;
// const PORT = 5e3;
app.listen(PORT, () => console.log(`Server running on port ${PORT}`));