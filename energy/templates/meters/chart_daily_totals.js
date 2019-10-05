
// Create empty data list
var data = [];

// Define chart layouts
var layout = {
    showlegend: true,
    bargap: 0.05,
    barmode: 'relative',
    legend: {
        orientation: 'h',
        x: 0, y: 1.2
    },
    xaxis: {
        showgrid: true,
    },
    yaxis: {
        title: 'kWh/day',
    },
    marker: {
        line: {
            width: 1.5
        }
    }
};


function onDataSetReceived(data) {
    onDataReceived(data.consumption);
    onDataReceived(data.controlled);
    onDataReceived(data.generation);
}

function onDataReceived(series) {
    // Push the new data onto our existing data array

    var x = [];
    var y = [];
    for (var i = 0; i < series.data.length; i++) {
        row = series.data[i];
        xVal = row[0]
        yVal = row[1]
        x.push(xVal);
        y.push(yVal);
    }

    var trace = {
        type: 'bar',
        x: x,
        y: y,
        name: series.label
    };
    if ("color" in series) {
        trace.line = { "color": series.color }
    };

    data.push(trace); // Add data to dataset

    // Plot the chart (or refresh with new data)
    var graphDiv = document.getElementById('load');
    Plotly.react(graphDiv, data, layout);

    // hide loading image when done plotting
    var loadImg = document.getElementById('load-loading');
    loadImg.style.visibility = 'hidden';
}

$.ajax({
    url: "daily_totals.json",
    type: "GET",
    dataType: "json",
    success: onDataSetReceived,
    error: function (XMLHttpRequest, textStatus, errorThrown) {
        alert("Error loading daily totals " + errorThrown);
    }
});

