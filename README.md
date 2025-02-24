# Combined Flask and Quart App

This repository contains a combined Flask and Quart application that integrates the Met Museum API and Spotify API to provide a unique experience based on user preferences for moods, art styles, and subjects.

## Features

- **Flask (Met Museum)**: Fetches artwork based on moods, art styles, and subjects.
- **Quart (Spotify)**: Fetches music recommendations based on moods and genres.
- **Combined Results**: Provides a combined view of artwork and music recommendations.

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/(yourusername)/combined_flask_quart_app.git
    cd combined_flask_quart_app
    ```

    *Replace "yourusername with your actual username"*

2. Create a virtual environment and activate it:
    ```sh
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

4. Set up environment variables:
    ```sh
    cp .env.example .env
    # Edit .env to include your Spotify API credentials
    ```

## Running the Application

1. Start the Flask and Quart servers:
    ```sh
    python combined_flask_quart_app.py
    ```

2. Access the application:
    - Flask (Met Museum): `http://127.0.0.1:3000`
    - Quart (Spotify): `http://127.0.0.1:3001`

## Usage

- **Home Page**: Provides an interface to select moods, art styles, and subjects.
- **Results Page**: Displays combined results from the Met Museum and Spotify based on user preferences.
- **Surprise Me**: Fetches random artwork and music recommendations.

## Contributing

1. Fork the repository.
2. Create a new branch. Example:(`git checkout -b feature-branch`).
3. Commit your changes. Example: (`git commit -am 'Add new feature'`).
4. Push to the branch. Example: (`git push origin feature-branch`).
5. Create a new Pull Request.

## License

This project is licensed under the MIT License.

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/)
- [Quart](https://pgjones.gitlab.io/quart/)
- [Met Museum API](https://metmuseum.github.io/)
- [Spotify API](https://developer.spotify.com/documentation/web-api/)

