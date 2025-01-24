const VideoProcessor = () => {
    const [selectedFile, setSelectedFile] = React.useState(null);
    const [isUploading, setIsUploading] = React.useState(false);
    const [error, setError] = React.useState(null);
    const [results, setResults] = React.useState(null);
    const fileInputRef = React.useRef(null);

    const allowedTypes = [
        'video/mp4', 'video/avi', 'video/quicktime', 
        'video/x-matroska', 'audio/mpeg'
    ];

    const handleFileSelect = (event) => {
        const file = event.target.files[0];
        const fileExtension = file?.name?.split('.').pop()?.toLowerCase();
        if (file && (allowedTypes.includes(file.type) || fileExtension === 'mp3')) {
            setSelectedFile(file);
            setError(null);
        } else {
            setError('Please select a valid video or audio file (MP4, AVI, MOV, MKV, or MP3)');
            setSelectedFile(null);
        }
    };

    const handleDragOver = (event) => {
        event.preventDefault();
    };

    const handleDrop = (event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        const fileExtension = file?.name?.split('.').pop()?.toLowerCase();
        if (file && (allowedTypes.includes(file.type) || fileExtension === 'mp3')) {
            setSelectedFile(file);
            setError(null);
        } else {
            setError('Please select a valid video or audio file (MP4, AVI, MOV, MKV, or MP3)');
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', selectedFile.name.split('.')[0]);
        formData.append('type', selectedFile.type.split('/')[0]); // 'video' or 'audio'

        try {
            const response = await fetch('/api/v1/process', {
                method: 'POST',
                body: formData,
            });

            let data;
            try {
                data = await response.json();
            } catch (err) {
                throw new Error('Failed to parse server response. Please try again.');
            }

            if (!response.ok) {
                const errorMessage = data.error || data.message || 'Failed to process file';
                throw new Error(errorMessage);
            }

            setResults(data.files);
            setSelectedFile(null);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setIsUploading(false);
        }
    };

    return React.createElement('div', { className: 'w-full max-w-3xl mx-auto p-4 space-y-4' },
        // Upload Card
        React.createElement('div', { className: 'bg-white rounded-lg shadow p-6' },
            React.createElement('h2', { className: 'text-xl font-bold mb-2' }, 'Video or Audio Processing'),
            React.createElement('p', { className: 'text-gray-600 mb-4' }, 
                'Upload a video or audio file to generate transcription, summary, and notes'
            ),
            
            // Upload Area
            React.createElement('div', {
                className: 'border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors',
                onClick: () => fileInputRef.current?.click(),
                onDragOver: handleDragOver,
                onDrop: handleDrop
            },
                React.createElement('input', {
                    type: 'file',
                    ref: fileInputRef,
                    onChange: handleFileSelect,
                    accept: '.mp4,.avi,.mov,.mkv,.mp3',
                    className: 'hidden'
                }),
                React.createElement('div', { className: 'mb-4' },
                    React.createElement('svg', {
                        className: 'mx-auto h-12 w-12 text-gray-400',
                        fill: 'none',
                        viewBox: '0 0 24 24',
                        stroke: 'currentColor'
                    },
                        React.createElement('path', {
                            strokeLinecap: 'round',
                            strokeLinejoin: 'round',
                            strokeWidth: 2,
                            d: 'M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12'
                        })
                    )
                ),
                React.createElement('p', { className: 'text-sm text-gray-600' },
                    'Drag and drop a video or audio file here, or click to select'
                ),
                React.createElement('p', { className: 'text-xs text-gray-500 mt-1' },
                    'Supports MP4, AVI, MOV, MKV, and MP3'
                )
            ),





            // Selected File
            selectedFile && React.createElement('div', { className: 'mt-4' },
                React.createElement('div', { className: 'flex items-center gap-2 text-sm text-gray-600' },
                    React.createElement('svg', {
                        className: 'h-4 w-4',
                        fill: 'none',
                        viewBox: '0 0 24 24',
                        stroke: 'currentColor'
                    },
                        React.createElement('path', {
                            strokeLinecap: 'round',
                            strokeLinejoin: 'round',
                            strokeWidth: 2,
                            d: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z'
                        })
                    ),
                    React.createElement('span', null, selectedFile.name)
                ),
                React.createElement('button', {
                    onClick: handleUpload,
                    disabled: isUploading,
                    className: 'mt-4 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed'
                }, isUploading ? 'Processing...' : 'Process File')
            )
        ),

        // Error Alert
        error && React.createElement('div', { className: 'bg-red-50 border-l-4 border-red-400 p-4 rounded' },
            React.createElement('div', { className: 'flex' },
                React.createElement('div', { className: 'flex-shrink-0' },
                    React.createElement('svg', {
                        className: 'h-5 w-5 text-red-400',
                        viewBox: '0 0 20 20',
                        fill: 'currentColor'
                    },
                        React.createElement('path', {
                            fillRule: 'evenodd',
                            d: 'M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z',
                            clipRule: 'evenodd'
                        })
                    )
                ),
                React.createElement('div', { className: 'ml-3' },
                    React.createElement('p', { className: 'text-sm text-red-700' }, error)
                )
            )
        ),


        // Results
        results && React.createElement('div', { className: 'bg-white rounded-lg shadow p-6' },
            React.createElement('h3', { className: 'text-lg font-semibold mb-4' }, 'Processing Results'),
            React.createElement('div', { className: 'space-y-4' },
                Object.entries(results).map(([type, filename]) =>
                    React.createElement('div', { key: type, className: 'flex items-center gap-2' },
                        React.createElement('svg', {
                            className: `h-4 w-4 ${
                                type === 'stats' ? 'text-purple-600' : 'text-green-600'
                            }`,
                            fill: 'none',
                            viewBox: '0 0 24 24',
                            stroke: 'currentColor'
                        },
                            React.createElement('path', {
                                strokeLinecap: 'round',
                                strokeLinejoin: 'round',
                                strokeWidth: 2,
                                d: type === 'stats' 
                                    ? 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z'
                                    : 'M5 13l4 4L19 7'
                            })
                        ),
                        React.createElement('span', { className: 'text-sm font-medium capitalize' },
                            `${type}:`
                        ),
                        React.createElement('span', { className: 'text-sm text-gray-600' },
                            filename
                        )
                    )
                )
            )
        )
    );
};