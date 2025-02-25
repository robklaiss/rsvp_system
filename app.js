const express = require('express');
const path = require('path');
const app = express();
const basePort = process.env.PORT || 5000;

// Middleware to parse JSON bodies
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const startServer = (port) => {
  const server = app.listen(port, '0.0.0.0', () => {
    console.log(`Server running at http://localhost:${server.address().port}`);
  }).on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`Port ${port} in use, trying ${port + 1}`);
      startServer(port + 1);
    } else {
      console.error('Server error:', err);
      process.exit(1);
    }
  });
};

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.get('/admin', (req, res) => {
  res.json({
    status: 'success',
    message: 'Admin dashboard',
    features: ['User management', 'Event management', 'RSVP tracking']
  });
});

app.post('/register', (req, res) => {
  const { name, email, eventId } = req.body;
  res.json({
    status: 'success',
    message: 'Registration successful',
    data: { name, email, eventId }
  });
});

app.get('/status', (req, res) => {
  res.json({
    status: 'operational',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

startServer(basePort);
