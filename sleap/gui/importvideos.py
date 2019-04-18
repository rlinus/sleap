"""
Interface to handle the UI for importing videos.

Usage:

>>> import_list = ImportVideos().go()

This will show the user a file-selection dialog, and then a second dialog
to select the import parameters for each file.

It returns a list with data about each file selected by the user.
In particular, we'll have the name of the file and all of the parameters
relevant for that specific type of file. It also includes a reference
to the relevant method of :class:`Video`.

For each `item` in `import_list`, we can load the video by calling this
method while passing the user-selected params as the named parameters:

>>> vid = item["video_class"](**item["params"])
"""

from PySide2.QtCore import Qt, QRectF, Signal
from PySide2.QtWidgets import QApplication, QLayout, QVBoxLayout, QHBoxLayout, QFrame
from PySide2.QtWidgets import QFileDialog, QDialog, QWidget, QLabel, QScrollArea
from PySide2.QtWidgets import QPushButton, QButtonGroup, QRadioButton, QCheckBox, QComboBox, QStackedWidget

from sleap.gui.video import GraphicsView
from sleap.io.video import Video, HDF5Video, MediaVideo

import h5py
import qimage2ndarray

class ImportVideos:
    """Class to handle video importing UI."""
    
    def __init__(self):
        self.result = []
    
    def go(self):
        """Runs the import UI.
        
        1. Show file selection dialog.
        2. Show import parameter dialog with widget for each file.
        
        Args:
            None.
        Returns:
            List with dict of the parameters for each file to import.
        """
        dialog = QFileDialog()
        #dialog.setOption(QFileDialog.Option.DontUseNativeDialogs, True)
        file_names, filter = dialog.getOpenFileNames(
                                None,
                                "Select videos to import...", # dialogue title
                                ".", # initial path
                                "Any Video (*.h5 *.hd5v *.mp4 *.avi);;HDF5 (*.h5 *.hd5v);;Media Video (*.mp4 *.avi);;Any File (*.*)", # filters
                                #options=QFileDialog.DontUseNativeDialog
                                )
        if len(file_names) > 0:
            importer = ImportParamDialog(file_names)
            importer.accepted.connect(lambda:importer.get_data(self.result))
            importer.exec_()
        return self.result

class ImportParamDialog(QDialog):
    """Dialog for selecting parameters with preview when importing video.
    
    Args:
        file_names (list): List of files we want to import.
    """

    def __init__(self, file_names:list, *args, **kwargs):
        super(ImportParamDialog, self).__init__(*args, **kwargs)
        
        self.import_widgets = []
        
        self.setWindowTitle("Video Import Options")
        
        self.import_types = [
            {
                "video_type": "hdf5",
                "match": "h5,hdf5",
                "video_class": Video.from_hdf5,
                "params": [
                    {
                        "name": "dataset",
                        "type": "function_menu",
                        "options": "_get_h5_dataset_options"
                    },
                    {
                        "name": "input_format",
                        "type": "radio",
                        "options": "channels_first,channels_last"
                    }
                ]
            },
            {
                "video_type": "mp4",
                "match": "mp4,avi",
                "video_class": Video.from_media,
                "params": [
                    {
                        "name": "grayscale",
                        "type": "check"
                    }
                ]
            }
        ]
        
        outer_layout = QVBoxLayout()
        
        scroll_widget = QScrollArea()
        #scroll_widget.setWidgetResizable(False)
        scroll_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_items_widget = QWidget()
        scroll_layout = QVBoxLayout()
        for file_name in file_names:
            if file_name:
                this_type = None
                for import_type in self.import_types:
                    if import_type.get("match",None) is not None:
                        if file_name.endswith(tuple(import_type["match"].split(","))):
                            this_type = import_type
                            break
                if this_type is not None:
                    import_item_widget = ImportItemWidget(file_name, this_type)
                    self.import_widgets.append(import_item_widget)
                    scroll_layout.addWidget(import_item_widget)
                else:
                    raise Exception("No match found for file type.")
        scroll_items_widget.setLayout(scroll_layout)
        scroll_widget.setWidget(scroll_items_widget)
        outer_layout.addWidget(scroll_widget)
        
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        import_button = QPushButton("Import")
        import_button.setDefault(True)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(import_button)
        
        outer_layout.addLayout(button_layout)
        
        self.setLayout(outer_layout)
        
        import_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_data(self, import_result = None):
        """Method to get results from import.

        Args:
            import_result (optional): If specified, we'll insert data into this.

        Returns:
            List of dicts with data for each (enabled) imported file.
        """
        # we don't want to set default to [] because that persists
        if import_result is None:
            import_result = []
        for import_item in self.import_widgets:
            if import_item.is_enabled():
                import_result.append(import_item.get_data())
        return import_result

    def boundingRect(self) -> QRectF:
        """Method required by Qt."""
        return QRectF()

    def paint(self, painter, option, widget=None):
        """Method required by Qt."""
        pass

class ImportItemWidget(QFrame):
    """Widget for selecting parameters with preview when importing video.

    Args:
        file_path (str): Full path to selected video file.
        import_type (dict): Data about user-selectable import parameters.
    """
    
    def __init__(self, file_path: str, import_type: dict, *args, **kwargs):
        super(ImportItemWidget, self).__init__(*args, **kwargs)
        
        self.file_path = file_path
        self.import_type = import_type
        self.video = None
        
        import_item_layout = QVBoxLayout()
        
        self.enabled_checkbox_widget = QCheckBox(self.file_path)
        self.enabled_checkbox_widget.setChecked(True)
        import_item_layout.addWidget(self.enabled_checkbox_widget)
        
        #import_item_layout.addWidget(QLabel(self.file_path))
        inner_layout = QHBoxLayout()
        self.options_widget = ImportParamWidget(parent=self, file_path = self.file_path, import_type = self.import_type)
        self.preview_widget = VideoPreviewWidget(parent=self)
        self.preview_widget.setFixedSize(200, 200)
        
        self.enabled_checkbox_widget.stateChanged.connect(
            lambda state:self.options_widget.setEnabled(state == Qt.Checked)
        )
        
        inner_layout.addWidget(self.options_widget)
        inner_layout.addWidget(self.preview_widget)
        import_item_layout.addLayout(inner_layout)
        self.setLayout(import_item_layout)
        
        self.setFrameStyle(QFrame.Panel)
        
        self.options_widget.changed.connect(self.update_video)
        self.update_video()

    def is_enabled(self):
        """Am I enabled?

        Our UI provides a way to enable/disable this item (file).
        We only want to import enabled items.

        Returns:
            Boolean: Am I enabled?
        """
        return self.enabled_checkbox_widget.isChecked()

    def get_data(self) -> dict:
        """Get all data (fixed and user-selected) for imported video.
        
        Returns:
            Dict with data for this video.
        """
        
        video_data = {
                        "params": self.options_widget.get_values(),
                        "video_type": self.import_type["video_type"],
                        "video_class": self.import_type["video_class"],
                     }
        return video_data

    def update_video(self):
        """Update preview video using current param values.
        
        Returns:
            None.
        """
        
        video_params = self.options_widget.get_values()
        try:
            if self.import_type["video_class"] is not None:
                self.video = self.import_type["video_class"](**video_params)
            else:
                self.video = None
            
            self.preview_widget.load_video(self.video)
        except Exception as e:
            print(e)
            # if we got an error showing video with those settings, clear the video preview
            self.video = None
            self.preview_widget.clear_video()

    def boundingRect(self) -> QRectF:
        """Method required by Qt."""
        return QRectF()

    def paint(self, painter, option, widget=None):
        """Method required by Qt."""
        pass

class ImportParamWidget(QWidget):
    """Widget for allowing user to select video parameters.

    Args:
        file_path: file path/name
        import_type: data about the parameters for this type of video

    Note:
        Object is a widget with the UI for params specific to this video type.
    """

    changed = Signal()

    def __init__(self, file_path:str, import_type:dict, *args, **kwargs):
        super(ImportParamWidget, self).__init__(*args, **kwargs)
        
        self.file_path = file_path
        self.import_type = import_type
        self.widget_elements = {}
        self.video_params = {}
        
        option_layout = self.make_layout()
        #self.changed.connect( lambda: print(self.get_values()) )
        
        self.setLayout(option_layout)
    
    def make_layout(self) -> QLayout:
        """Builds the layout of widgets for user-selected import parameters."""
        
        param_list = self.import_type["params"]
        widget_layout = QVBoxLayout()
        widget_elements = dict()
        for param_item in param_list:
            name = param_item["name"]
            type = param_item["type"]
            options = param_item.get("options",None)
            if type == "radio":
                radio_group = QButtonGroup(parent=self)
                option_list = options.split(",")
                selected_option = option_list[0]
                for option in option_list:
                    btn_widget = QRadioButton(option)
                    if option == selected_option:
                        btn_widget.setChecked(True)
                    widget_layout.addWidget(btn_widget)
                    radio_group.addButton(btn_widget)
                radio_group.buttonToggled.connect(lambda:self.changed.emit())
                widget_elements[name] = radio_group
            elif type == "check":
                check_widget = QCheckBox(name)
                check_widget.stateChanged.connect(lambda:self.changed.emit())
                widget_layout.addWidget(check_widget)
                widget_elements[name] = check_widget
            elif type == "function_menu":
                list_widget = QComboBox()
                # options has name of method which returns list of options
                option_list = getattr(self, options)()
                for option in option_list:
                    list_widget.addItem(option)
                list_widget.currentIndexChanged.connect(lambda:self.changed.emit())
                widget_layout.addWidget(list_widget)
                widget_elements[name] = list_widget
            self.widget_elements = widget_elements
        return widget_layout
    
    def get_values(self):
        """Method to get current user-selected values for import parameters.

        Args:
            None.

        Returns:
            Dict of param keys/values.

        Note:
            It's easiest if the return dict matches the arguments we need
            for the Video object, so we'll add the file name to the dict
            even though it's not a user-selectable param.
        """
        param_list = self.import_type["params"]
        param_values = {}
        param_values["file"] = self.file_path
        for param_item in param_list:
            name = param_item["name"]
            type = param_item["type"]
            value = None
            if type == "radio":
                value = self.widget_elements[name].checkedButton().text()
            elif type == "check":
                value = self.widget_elements[name].isChecked()
            elif type == "function_menu":
                value = self.widget_elements[name].currentText()
            param_values[name] = value
        return param_values
    
    def _get_h5_dataset_options(self) -> list:
        """Method to get a list of all datasets in hdf5 file.

        Args:
            None.

        Returns:
            List of datasets in the hdf5 file for our import item.

        Note:
            This is used to populate the "function_menu"-type param.
        """
        try:
            with h5py.File(self.file_path,"r") as f:
                options = self._find_h5_datasets("",f)
        except Exception as e:
            options = []
        return options
    
    def _find_h5_datasets(self, data_path, data_object) -> list:
        """Recursively find datasets in hdf5 file."""
        options = []
        for key in data_object.keys():
            if isinstance(data_object[key], h5py._hl.dataset.Dataset):
                if len(data_object[key].shape) == 4:
                    options.append(data_path + "/" + key)
            elif isinstance(data_object[key], h5py._hl.group.Group):
                options.extend(self._find_h5_datasets(data_path + "/" + key, data_object[key]))
        return options

    def boundingRect(self) -> QRectF:
        """Method required by Qt."""
        return QRectF()

    def paint(self, painter, option, widget=None):
        """Method required by Qt."""
        pass


class VideoPreviewWidget(QWidget):
    """Widget to show video preview. Based on :class:`Video` class.

    Args:
        video: the video to show

    Returns:
        None.

    Note:
        This widget is used by ImportItemWidget.
    """

    def __init__(self, video: Video = None, *args, **kwargs):
        super(VideoPreviewWidget, self).__init__(*args, **kwargs)
        # widgets to include
        self.view = GraphicsView()
        self.video_label = QLabel()
        # layout for widgets
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.view)
        self.layout.addWidget(self.video_label)
        self.setLayout(self.layout)
        self.view.show()
        
        if video is not None:
            self.load_video(video)
    
    def clear_video(self):
        """Clear the video preview."""
        self.view.clear()
    
    def load_video(self, video: Video, initial_frame=0, plot=True):
        """Load the video preview and display label text."""
        self.video = video
        self.frame_idx = initial_frame
        label = "(%d, %d), %d f, %d c" % (self.video.width, self.video.height, self.video.frames, self.video.channels)
        self.video_label.setText(label)
        if plot:
            self.plot(initial_frame)
    
    def plot(self, idx=0):
        """Show the video preview."""
        if self.video is None:
            return
        
        # Get image data
        frame = self.video.get_frame(idx)
        # Clear existing objects
        self.view.clear()
        # Convert ndarray to QImage
        image = qimage2ndarray.array2qimage(frame)
        # Display image
        self.view.setImage(image)

    def boundingRect(self) -> QRectF:
        """Method required by Qt."""
        return QRectF()

    def paint(self, painter, option, widget=None):
        """Method required by Qt."""
        pass


if __name__ == "__main__":

    app = QApplication([])
    
    import_list = ImportVideos().go()
    
    for import_item in import_list:
        vid = import_item["video_class"](**import_item["params"])
        print("Imported video data: (%d, %d), %d f, %d c" % (vid.width, vid.height, vid.frames, vid.channels))
