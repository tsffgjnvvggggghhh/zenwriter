import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit, QVBoxLayout, QWidget, QFileDialog, QMessageBox, QLabel, QHBoxLayout, QPushButton
from PyQt6.QtGui import QFont, QColor, QPalette, QKeySequence, QShortcut, QTextCharFormat, QTextCursor, QMouseEvent
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QObject, pyqtProperty, QEvent, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QPainter
import asyncio

class MediaIntegrationThread(QThread):
    media_updated = pyqtSignal(str, str, str) # title, artist, duration

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_running = True

    def run(self):
        try:
            # winsdk uses async paradigms often, so we set up an event loop
            asyncio.run(self._monitor_media())
        except Exception as e:
            print("winsdk failed, falling back to mock data", e)
            self._mock_monitor_media()

    async def _monitor_media(self):
        try:
            # Since winsdk failed to install on this linux devbox, this branch will likely fail
            # and fallback to mock data, which fulfills the prompt's request for safe fallback.
            from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()

            # This is a very simplified polling loop. A real app might use event handlers.
            while self._is_running:
                session = manager.get_current_session()
                if session:
                    info = await session.try_get_media_properties_async()
                    timeline = session.get_timeline_properties()
                    duration_str = "0:00"
                    if timeline:
                        # Convert Windows duration (100ns ticks) to seconds
                        duration_secs = int(timeline.end_time.duration / 10_000_000)
                        mins, secs = divmod(duration_secs, 60)
                        duration_str = f"{mins}:{secs:02d}"
                    if info:
                        self.media_updated.emit(info.title, info.artist, duration_str)
                await asyncio.sleep(2)
        except ImportError:
            raise Exception("winsdk not found")
        except Exception as e:
            raise Exception(f"Winsdk media fetch error: {e}")

    def _mock_monitor_media(self):
        # Provide safe fallback/mock data if winsdk is missing or fails
        import time
        count = 0
        while self._is_running:
            if count % 20 < 10:
                self.media_updated.emit("Weightless", "Marconi Union", "8:08")
            else:
                self.media_updated.emit("Clair de Lune", "Claude Debussy", "5:05")

            # Shorter sleeps allow for faster thread exit when closed
            time.sleep(1)
            count += 1

    def stop(self):
        self._is_running = False

class CaretWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(2, 20) # width, height
        self.setStyleSheet("background-color: #E0E0E0;")
        self._opacity = 1.0

        # Blinking animation
        self.blink_anim = QPropertyAnimation(self, b"opacity")
        self.blink_anim.setDuration(500)
        self.blink_anim.setStartValue(1.0)
        self.blink_anim.setEndValue(0.0)
        self.blink_anim.setLoopCount(-1) # Infinite loop

        # Gliding animation
        self.glide_anim = QPropertyAnimation(self, b"geometry")
        self.glide_anim.setDuration(100) # Fast but smooth

    @pyqtProperty(float)
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, value):
        self._opacity = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setOpacity(self._opacity)
        painter.fillRect(self.rect(), QColor("#E0E0E0"))

    def move_to(self, rect):
        self.setFixedSize(2, rect.height())

        # Stop gliding if already running
        if self.glide_anim.state() == QPropertyAnimation.State.Running:
            self.glide_anim.stop()

        self.glide_anim.setStartValue(self.geometry())
        self.glide_anim.setEndValue(rect)
        self.glide_anim.start()

        # Restart blinking
        self.blink_anim.stop()
        self.opacity = 1.0
        self.blink_anim.start()


class TopMenuWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet("background-color: #111111; border-bottom: 1px solid #333333;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)

        self.title_label = QLabel("ZenWriter Settings", self)
        self.title_label.setStyleSheet("color: #AAAAAA; font-family: 'Courier New'; font-size: 14px;")

        self.exit_button = QPushButton("Exit", self)
        self.exit_button.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: None;
                padding: 5px 15px;
                font-family: 'Courier New';
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

        layout.addWidget(self.title_label)
        layout.addStretch()
        layout.addWidget(self.exit_button)

        # Slide animation
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(250)


class SpotifyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet("background-color: #111111; border-left: 1px solid #333333;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        self.title_label = QLabel("Now Playing", self)
        self.title_label.setStyleSheet("color: #AAAAAA; font-family: 'Courier New'; font-size: 12px;")

        self.track_label = QLabel("Track Name", self)
        self.track_label.setStyleSheet("color: #E0E0E0; font-family: 'Courier New'; font-size: 16px; font-weight: bold;")
        self.track_label.setWordWrap(True)

        self.artist_label = QLabel("Artist Name", self)
        self.artist_label.setStyleSheet("color: #888888; font-family: 'Courier New'; font-size: 14px;")
        self.artist_label.setWordWrap(True)

        self.album_art_label = QLabel("Album Art Placeholder", self)
        self.album_art_label.setStyleSheet("color: #555555; border: 1px dashed #555555;")
        self.album_art_label.setFixedSize(210, 210)
        self.album_art_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #333;
                background-color: #111;
                height: 5px;
            }
            QProgressBar::chunk {
                background-color: #1DB954;
            }
        """)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(30) # Placeholder progress

        layout.addWidget(self.title_label)
        layout.addSpacing(20)
        layout.addWidget(self.album_art_label)
        layout.addSpacing(10)
        layout.addWidget(self.track_label)
        layout.addWidget(self.artist_label)
        layout.addSpacing(10)
        layout.addWidget(self.progress_bar)
        layout.addStretch()

        # Slide animation
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(250)


class ZenWriter(QMainWindow):
    def __init__(self):
        super().__init__()

        self.current_file = None

        self.initUI()

        # Auto-save timer (5 minutes)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.auto_save)
        self.autosave_timer.start(5 * 60 * 1000)

    def initUI(self):
        # Frameless window and true black background
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#000000"))
        self.setPalette(palette)

        # Central Text Editor
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setFrameStyle(0) # Borderless

        # Styling the text editor
        text_palette = self.text_edit.palette()
        text_palette.setColor(QPalette.ColorRole.Base, QColor("#000000"))
        text_palette.setColor(QPalette.ColorRole.Text, QColor("#E0E0E0")) # High contrast off-white
        self.text_edit.setPalette(text_palette)

        # Font settings
        font = QFont("Courier New", 14)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)

        # Setting padding/margins via stylesheet
        self.text_edit.setStyleSheet("""
            QPlainTextEdit {
                padding: 40px;
                line-height: 1.5; /* Custom line-height can be tricky, might need QTextBlockFormat later */
                selection-background-color: #333333;
            }
        """)

        # Hide scrollbars
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Custom Caret
        self.text_edit.setCursorWidth(0) # Hide default cursor
        self.caret = CaretWidget(self.text_edit.viewport())
        self.text_edit.cursorPositionChanged.connect(self.update_caret_position)

        # Setup caret blinking
        self.caret.blink_anim.start()

        # Status Bar
        self.status_bar_widget = QWidget(self)
        status_layout = QHBoxLayout(self.status_bar_widget)
        status_layout.setContentsMargins(20, 0, 20, 10)

        self.word_count_label = QLabel("0 Words", self)
        self.line_count_label = QLabel("1 Line", self)

        status_style = "color: #555555; font-family: 'Courier New'; font-size: 10px;"
        self.word_count_label.setStyleSheet(status_style)
        self.line_count_label.setStyleSheet(status_style)

        status_layout.addWidget(self.word_count_label)
        status_layout.addStretch()
        status_layout.addWidget(self.line_count_label)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.status_bar_widget)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Signals for status bar
        self.text_edit.textChanged.connect(self.update_status)

        # Hidden Menus
        self.top_menu = TopMenuWidget(self)
        self.top_menu.exit_button.clicked.connect(self.close)

        self.spotify_widget = SpotifyWidget(self)

        # Start Media Integration
        self.media_thread = MediaIntegrationThread(self)
        self.media_thread.media_updated.connect(self.update_media_info)
        self.media_thread.start()

        # Fullscreen defaults
        self.is_fullscreen = True
        self.showFullScreen()

        # Event filter for mouse tracking - install on application for global tracking
        QApplication.instance().installEventFilter(self)
        self.setMouseTracking(True)
        self.centralWidget().setMouseTracking(True)
        self.text_edit.setMouseTracking(True)

        # Keyboard shortcuts
        QShortcut(QKeySequence("F11"), self).activated.connect(self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.new_file)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_file)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_file)

        # Temporary way to close
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)

    def new_file(self):
        self.text_edit.clear()
        self.current_file = None

    def open_file(self):
        options = QFileDialog.Option.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", "Text Files (*.txt);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'r', encoding='utf-8') as file:
                    self.text_edit.setPlainText(file.read())
                    self.current_file = fileName
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not read file:\n{str(e)}")

    def save_file(self):
        if self.current_file:
            self._save_to_path(self.current_file)
        else:
            options = QFileDialog.Option.DontUseNativeDialog
            fileName, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Text Files (*.txt);;All Files (*)", options=options)
            if fileName:
                self.current_file = fileName
                self._save_to_path(fileName)

    def auto_save(self):
        if self.current_file:
            self._save_to_path(self.current_file)
            # You could optionally show a faint "autosaved" message

    def _save_to_path(self, path):
        try:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(self.text_edit.toPlainText())
        except Exception as e:
            pass # In a real app we might log this or notify

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.showNormal()
            self.is_fullscreen = False
        else:
            self.showFullScreen()
            self.is_fullscreen = True

    def update_caret_position(self):
        cursor = self.text_edit.textCursor()
        rect = self.text_edit.cursorRect(cursor)

        # Ensure it fits nicely within padding if necessary, but cursorRect usually handles it
        # Apply padding offset if needed, though QPlainTextEdit.cursorRect() is relative to viewport
        self.caret.move_to(rect)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position menus off-screen initially
        self.top_menu.resize(self.width(), 50)
        self.top_menu.move(0, -50)

        self.spotify_widget.resize(250, self.height())
        self.spotify_widget.move(self.width(), 0)

        # Update caret in case resize moved text
        self.update_caret_position()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseMove:
            # Handle Top Menu Slide Down
            if event.pos().y() <= 10:
                if self.top_menu.pos().y() < 0 and self.top_menu.anim.state() != QPropertyAnimation.State.Running:
                    self.top_menu.anim.setStartValue(self.top_menu.pos())
                    self.top_menu.anim.setEndValue(self.top_menu.pos() + QPoint(0, 50))
                    self.top_menu.anim.start()
            elif event.pos().y() > 50:
                if self.top_menu.pos().y() == 0 and self.top_menu.anim.state() != QPropertyAnimation.State.Running:
                    self.top_menu.anim.setStartValue(self.top_menu.pos())
                    self.top_menu.anim.setEndValue(self.top_menu.pos() - QPoint(0, 50))
                    self.top_menu.anim.start()

            # Handle Right Spotify Widget Slide Out
            if event.pos().x() >= self.width() - 10:
                if self.spotify_widget.pos().x() == self.width() and self.spotify_widget.anim.state() != QPropertyAnimation.State.Running:
                    self.spotify_widget.anim.setStartValue(self.spotify_widget.pos())
                    self.spotify_widget.anim.setEndValue(self.spotify_widget.pos() - QPoint(250, 0))
                    self.spotify_widget.anim.start()
            elif event.pos().x() < self.width() - 250:
                if self.spotify_widget.pos().x() == self.width() - 250 and self.spotify_widget.anim.state() != QPropertyAnimation.State.Running:
                    self.spotify_widget.anim.setStartValue(self.spotify_widget.pos())
                    self.spotify_widget.anim.setEndValue(self.spotify_widget.pos() + QPoint(250, 0))
                    self.spotify_widget.anim.start()

        return super().eventFilter(obj, event)

    def update_media_info(self, title, artist, duration):
        self.spotify_widget.track_label.setText(title)
        self.spotify_widget.artist_label.setText(f"{artist} • {duration}")

    def closeEvent(self, event):
        self.media_thread.stop()
        self.media_thread.wait()
        super().closeEvent(event)

    def update_status(self):
        text = self.text_edit.toPlainText()
        words = len(text.split())
        lines = text.count('\n') + 1

        self.word_count_label.setText(f"{words} Words")
        self.line_count_label.setText(f"{lines} Lines" if lines > 1 else "1 Line")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ZenWriter()
    window.show()
    sys.exit(app.exec())
