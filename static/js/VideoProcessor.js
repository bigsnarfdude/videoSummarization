const VideoProcessor = () => {
    const [selectedFile, setSelectedFile] = React.useState(null);
    const [isUploading, setIsUploading] = React.useState(false);
    const [error, setError] = React.useState(null);
    const [results, setResults] = React.useState(null);
    const fileInputRef = React.useRef(null);

    const allowedTypes = ['video/mp4', 'video/avi', 'video/quicktime', 'video/x-matroska'];

    const handleFileSelect = (event) => {
        const file = event.target.files[0];
        if (file && allowedTypes.includes(file.type)) {
            setSelectedFile(file);
            setError(null);
        } else {
            setError('Please select a valid video file (MP4, AVI, MOV, or MKV)');
            setSelectedFile(null);
        }
    };

    const handleDragOver = (event) => {
        event.preventDefault();
    };

    const handleDrop = (event) => {
        event.preventDefault();
        const file = event.dataTransfer.files[0];
        if (file && allowedTypes.includes(file.type)) {
            setSelectedFile(file);
            setError(null);
        } else {
            setError('Please select a valid video file (MP4, AVI, MOV, or MKV)');
        }
    };

    const handleUpload = async () => {
        if (!selectedFile) return;

        setIsUploading(true);
        setError(null);

        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', selectedFile.name.split('.')[0]);

        try {
            const response = await fetch('/api/process', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process video');
            }

            setResults(data.files);
        } catch (err) {
            setError(err.message);
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="w-full max-w-3xl mx-auto p-4 space-y-4">
            {/* Upload Card */}
            <div className="bg-white rounded-lg shadow p-6">
                <h2 className="text-xl font-bold mb-2">Video Processing</h2>
                <p className="text-gray-600 mb-4">
                    Upload a video to generate transcription, summary, and notes
                </p>
                
                {/* Upload Area */}
                <div
                    className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors"
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                >
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        accept=".mp4,.avi,.mov,.mkv"
                        className="hidden"
                    />
                    <div className="mb-4">
                        <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                    </div>
                    <p className="text-sm text-gray-600">
                        Drag and drop a video file here, or click to select
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                        Supports MP4, AVI, MOV, and MKV
                    </p>
                </div>

                {/* Selected File */}
                {selectedFile && (
                    <div className="mt-4">
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                            </svg>
                            <span>{selectedFile.name}</span>
                        </div>
                        <button
                            onClick={handleUpload}
                            disabled={isUploading}
                            className="mt-4 w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed"
                        >
                            {isUploading ? 'Processing...' : 'Process Video'}
                        </button>
                    </div>
                )}
            </div>

            {/* Error Alert */}
            {error && (
                <div className="bg-red-50 border-l-4 border-red-400 p-4 rounded">
                    <div className="flex">
                        <div className="flex-shrink-0">
                            <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                            </svg>
                        </div>
                        <div className="ml-3">
                            <p className="text-sm text-red-700">{error}</p>
                        </div>
                    </div>
                </div>
            )}

            {/* Results */}
            {results && (
                <div className="bg-white rounded-lg shadow p-6">
                    <h3 className="text-lg font-semibold mb-4">Processing Results</h3>
                    <div className="space-y-4">
                        {Object.entries(results).map(([type, filename]) => (
                            <div key={type} className="flex items-center gap-2">
                                <svg className="h-4 w-4 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                <span className="text-sm font-medium capitalize">
                                    {type}:
                                </span>
                                <span className="text-sm text-gray-600">{filename}</span>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};
