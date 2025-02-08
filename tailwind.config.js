module.exports = {
    content: [
      "./templates/**/*.html", // Scan Flask templates
      "./static/js/**/*.js" // Include JS files if needed
    ],
    theme: {
      extend: {
        fontFamily: {
          sans: ['Helvetica', 'Arial', 'sans-serif'],
        },
      },
    },
    plugins: [],
  };