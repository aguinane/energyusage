
// Create empty data list
var data = [];

// Define chart layouts
var layout = {
    showlegend: true,
    bargap: 0.05,
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
};


function onDataReceived(series) {
    // Push the new data onto our existing data array

    var x = [];
    var y = [];
    for (var i = 0; i < series.consumption.data.length; i++) {
        row = series.consumption.data[i];
        xVal = row[0]
        yVal = row[1]
        x.push(xVal);
        y.push(yVal);
    }

    var trace = {
        type: 'bar',
        x: x,
        y: y,
        name: series.consumption.label
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
    url: "monthly_totals.json",
    type: "GET",
    dataType: "json",
    success: onDataReceived,
    error: function (XMLHttpRequest, textStatus, errorThrown) {
        alert("Error loading monthly totals " + errorThrown);
    }
});

